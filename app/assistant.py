"""One question, end to end (FT-10, FT-20).

read allowed sources (G1, G2) -> find candidates in memory -> ask the local model (G3) ->
answer check (G4) -> brief with quotes, coverage and the gate trace. Nothing is written to
disk at any step.
"""

import time
from datetime import datetime

from app import config, coverage, meetings, prompts
from app.broker import Broker
from app.gate import Checked, Given, check, instruction_units, parse_points
from app.images import ImageReader
from app.model import Model, complete_json
from app.policy import AccessPolicy
from app.search import Candidate, add_expansion, build_query, find
from app.store import SessionStore
from contracts.api import (
    Answer,
    AnswerKind,
    BriefPoint,
    Citation,
    Meeting,
    PointStatus,
    Progress,
)
from contracts.broker import SourceStatus
from contracts.errors import DeskThreadError
from contracts.gates import Gate, GateResult, Outcome
from contracts.items import Item, Unit

NOT_FOUND = "I could not find this in the notes you shared."
NO_SOURCES = "No source is switched on, so there is nothing I am allowed to read."


class Assistant:
    def __init__(
        self, broker: Broker, store: SessionStore, policy: AccessPolicy, model: Model
    ) -> None:
        self._broker, self._store, self._policy, self._model = broker, store, policy, model
        self._images = ImageReader(policy, store, model)
        self.questions = 0
        self.items_given = 0
        self.progress = Progress()  # which step a running question is on

    def forget(self) -> None:
        """Forget now: drop every item held in memory. The app stays open."""
        self._store.forget()
        self._images.forget()

    @property
    def readings_held(self) -> int:
        return self._images.held

    # ------------------------------------------------------------------ meetings (FT-34)
    def meetings(self, days: int = 7) -> list[Meeting]:
        self._store.refresh()
        return meetings.upcoming(self._store.items(), days)

    def prepare(self, meeting_id: str) -> Answer:
        meeting = next((m for m in self.meetings(days=30) if m.meeting_id == meeting_id), None)
        if meeting is None:
            return self.ask("What did I promise?")
        return self.ask(f"What did I promise {meeting.person}?", person=meeting.person)

    # ------------------------------------------------------------------ one question
    STEPS = (
        "Reading what you switched on",
        "Reading pictures",
        "Finding the right items",
        "Asking the AI on this Mac",
        "Checking the answer",
    )

    def _step(self, number: int) -> None:
        self.progress = Progress(step=self.STEPS[number - 1], number=number, of=len(self.STEPS))

    def ask(self, question: str, person: str | None = None) -> Answer:
        try:
            return self._ask(question, person)
        finally:
            self.progress = Progress()

    def _ask(self, question: str, person: str | None = None) -> Answer:
        started = time.monotonic()
        self.questions += 1
        trace: list[GateResult] = []
        allowed = [s for s in self._broker.states() if s.status is SourceStatus.ON]
        if not allowed:
            trace.append(_gate(Gate.G1_POLICY, Outcome.PASS, "every source is Off: nothing read"))
            return self._answer(AnswerKind.NO_SOURCES, question, NO_SOURCES, [], [], trace, started)

        self._step(1)
        self._store.refresh()  # read again each time: a deleted file is gone at once (U10)
        self._step(2)
        unread = self._images.read_pending()  # the local model reads new images
        items = self._store.items()
        coverage_note = (
            f"{len(items)} items readable in {len(allowed)} allowed sources; "
            f"{coverage.off_limits(self._broker)} off-limits files not opened"
        )
        trace.append(_gate(Gate.G1_POLICY, Outcome.PASS, coverage_note))

        self._step(3)
        query = build_query(question, person)
        calls_before = getattr(self._model, "calls", 0)
        try:
            if query.focus:
                # P3: the same local model suggests other words for the topic.
                suggested = complete_json(
                    self._model,
                    prompts.EXPAND.format(question=question, focus=", ".join(query.focus_words)),
                ).get("words", [])
                add_expansion(
                    query, [str(w) for w in suggested] if isinstance(suggested, list) else []
                )
            candidates = find(query, items)
            read_note = (
                f"searched {len(items)} items; {len(self._store.uncounted()) + unread} could not "
                f"be read; {len(candidates)} passed the relevance rule"
            )
            trace.append(_gate(Gate.G2_READ, Outcome.PASS, read_note))
            if not candidates:
                trace.append(_gate(Gate.G3_MODEL, Outcome.SKIPPED, "no note to show: not asked"))
                trace.append(_gate(Gate.G4_ANSWER, Outcome.PASS, "nothing relevant: not found"))
                return self._answer(
                    AnswerKind.NOT_FOUND, question, NOT_FOUND, [], [], trace, started
                )

            given = self._give(candidates)
            self._step(4)
            proposed = parse_points(
                complete_json(
                    self._model,
                    prompts.ANSWER.format(question=question, notes=_render(given)),
                )
            )
            self._step(5)
            points, result = check(query, proposed, given, self._model)
        except DeskThreadError as err:
            trace.append(_gate(Gate.G3_MODEL, Outcome.FAIL, f"the local model failed ({err.code})"))
            message = "The model on this laptop did not answer. Nothing was sent anywhere else."
            return self._answer(AnswerKind.NOT_FOUND, question, message, [], [], trace, started)
        calls = getattr(self._model, "calls", 0) - calls_before
        model_note = (
            f"{getattr(self._model, 'tag', config.MODEL_TAG)}, prompt {config.PROMPT_VERSION}, "
            f"on this laptop only, {calls} calls, no tools"
        )
        trace.append(_gate(Gate.G3_MODEL, Outcome.PASS, model_note))
        trace.append(result)
        self.items_given += len(given)
        kind = AnswerKind.BRIEF if points else AnswerKind.NOT_FOUND
        message = "" if points else NOT_FOUND
        return self._answer(kind, question, message, points, given, trace, started)

    # ------------------------------------------------------------------ helpers
    def _give(self, candidates: list[Candidate]) -> list[Given]:
        return [
            Given(alias=f"A{n}", item=c.item, withheld=frozenset(instruction_units(c.item)))
            for n, c in enumerate(candidates, 1)
        ]

    def _answer(
        self,
        kind: AnswerKind,
        question: str,
        message: str,
        points: list[Checked],
        given: list[Given],
        trace: list[GateResult],
        started: float,
    ) -> Answer:
        labels = {s.source_id: s.label for s in self._broker.states()}
        brief = tuple(
            BriefPoint(
                label=p.label,
                status=PointStatus(p.status),
                note=p.note,
                citations=tuple(_citation(item, unit, labels) for item, unit in p.cites),
            )
            for p in points
        )
        cited = {c.item_id for p in brief for c in p.citations}
        audit = len(self._broker.audit())
        trace = [*trace, _gate(Gate.G6_AUDIT, Outcome.PASS, f"{audit} lines, in memory only")]
        return Answer(
            kind=kind,
            question=question,
            points=brief,
            message=message,
            coverage=coverage.build(self._broker, self._store, len(given), len(cited)),
            gate_trace=tuple(trace),
            given_item_ids=tuple(g.item.item_id for g in given),
            seconds=round(time.monotonic() - started, 2),
        )


def _gate(gate: Gate, outcome: Outcome, detail: str) -> GateResult:
    return GateResult(gate=gate, outcome=outcome, detail=detail)


def _citation(item: Item, unit: Unit, labels: dict[str, str]) -> Citation:
    return Citation(
        item_id=item.item_id,
        unit=unit.number,
        quote=unit.text,  # copied from the note by code; the model never writes a quote
        source_id=item.source_id,
        source_label=labels.get(item.source_id, item.source_id),
        title=item.title,
        date=item.date,
        undated=item.undated,
        read_by_model=item.read_by_model,
    )


def _when(date: datetime | None) -> str:
    return date.strftime("%d %b %Y") if date else "undated"


def _render(given: list[Given]) -> str:
    """The notes as the model sees them: alias, kind, date, title, numbered lines."""
    blocks = []
    for g in given:
        head = f"[{g.alias}] {g.item.kind.value} | {_when(g.item.date)} | {g.item.title}"
        lines = [
            f"{u.number}. {prompts.WITHHELD if u.number in g.withheld else u.text}"
            for u in g.item.units
        ]
        blocks.append("\n".join([head, *lines]))
    return "\n\n".join(blocks)
