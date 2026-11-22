"""One question, end to end (FT-10, FT-20).

read allowed sources (G1, G2) -> find candidates in memory -> ask the local model (G3) ->
answer check (G4) -> brief with quotes, coverage and the gate trace. Nothing is written to
disk at any step.
"""

import re
import threading
import time
from datetime import datetime, timedelta

from app import config, coverage, meetings, prompts
from app.broker import Broker
from app.clock import now
from app.gate import (
    Checked,
    Given,
    check,
    instruction_units,
    left_out,
    matched_words,
    parse_points,
    summarise,
)
from app.images import ImageReader
from app.meaning import Meaning, likeness
from app.model import Model, complete_json
from app.policy import AccessPolicy
from app.search import (
    Candidate,
    Query,
    add_expansion,
    build_query,
    find,
    item_stems,
    names_in,
    stem,
    stems,
)
from app.store import SessionStore
from contracts.api import (
    Answer,
    AnswerKind,
    BriefPoint,
    Citation,
    DroppedQuote,
    ItemRef,
    Meeting,
    PointStatus,
    Preparing,
    Progress,
    RelatedRef,
    Unread,
)
from contracts.broker import SourceStatus
from contracts.errors import DeskThreadError, ErrorCode
from contracts.gates import Gate, GateResult, Outcome
from contracts.items import Item, ItemKind, Unit

READY_SECONDS = 4.0  # how long "Pictures ready" stays on the screen
NOT_FOUND = "I could not find this in the notes you shared."


class _StoppedError(Exception):
    """The user stopped the question."""


COMMITMENT_WORDS = frozenset(
    stem(w) for w in ("promise", "promised", "owe", "agreed", "commit", "todo", "pending", "still")
)
NO_SOURCES = "No source is switched on, so there is nothing I am allowed to read."


class Assistant:
    def __init__(
        self, broker: Broker, store: SessionStore, policy: AccessPolicy, model: Model
    ) -> None:
        self._broker, self._store, self._policy, self._model = broker, store, policy, model
        self._images = ImageReader(policy, store, model)
        self._meaning = Meaning(model)
        # Other ways the user writes a name, set on the Access screen; in memory only.
        self.spellings: dict[str, tuple[str, ...]] = {}
        self.questions = 0
        self.items_given = 0
        self.given_by: dict[str, int] = {}  # source id -> items shown to the AI
        self.progress = Progress()  # which step a running question is on
        self.preparing = Preparing()  # pictures being read after a switch is turned on
        self._prep_lock = threading.Lock()
        self._prep_jobs = 0
        self._ready_until = 0.0
        self._stop = threading.Event()  # set when the user stops the running question

    def forget(self) -> None:
        """Forget now: drop every item held in memory. The app stays open."""
        self._store.forget()
        self._images.forget()
        self._meaning.forget()

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
            return self.ask("What is coming up?")
        item = self._store.get(meeting_id)
        people = (_attendees(item) if item else []) or ([meeting.person] if meeting.person else [])
        if len(people) == 1:
            return self.ask(f"What did I promise {people[0]}?", person=people[0])
        if people:  # a team meeting: what was promised to each of them
            names = f"{', '.join(people[:-1])} and {people[-1]}"
            return self.ask(f"What did I promise {names}?")
        return self.ask(f"What do I need to know for {meeting.title}?")

    # ------------------------------------------------------------------ one question
    STEPS = (
        "Reading your folders",
        "Reading pictures",
        "Finding the right items",
        "Asking the AI on this Mac",
        "Checking the answer",
    )

    def _step(self, number: int, detail: str = "") -> None:
        if self._stop.is_set():
            raise _StoppedError
        self.progress = Progress(
            step=self.STEPS[number - 1], number=number, of=len(self.STEPS), detail=detail
        )

    def cancel(self) -> None:
        """Stop the running question at its next step. A request already with the AI is
        waited for (it cannot be interrupted), but its answer is thrown away."""
        self._stop.set()
        abort = getattr(self._model, "abort", None)
        if callable(abort):
            abort()  # cut the request that is with the AI right now

    def _check_stop(self) -> None:
        if self._stop.is_set():
            raise _StoppedError

    def ask(self, question: str, person: str | None = None) -> Answer:
        self._stop.clear()
        self._left: dict[str, int] = {}
        self._dropped: list[tuple[Item, Unit, str]] = []  # quotes the check dropped
        self._seen: tuple[Query, dict[str, tuple[str, str]]] | None = None  # query, linked
        started = time.monotonic()
        try:
            answer = self._ask(question, person)
            choice = config.model_choice(getattr(self._model, "tag", config.MODEL_TAG))
            named = choice.name if choice else getattr(self._model, "tag", "")
            kept = {k: v for k, v in self._left.items() if v > 0}
            update = {"model_name": named, "left_out": kept, **self._details(answer)}
            return answer.model_copy(update=update)
        except _StoppedError:
            return self._answer(AnswerKind.STOPPED, question, "Stopped.", [], [], [], started)
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
        unread = self._images.read_pending(  # pictures not read yet (normally none: see below)
            lambda done, total, _phase: self._step(2, f"picture {done} of {total}"),
            self._check_stop,
        )
        items = self._store.items()
        coverage_note = (
            f"{len(items)} items readable in {len(allowed)} allowed sources; "
            f"{coverage.off_limits(self._broker)} off-limits files not opened"
        )
        trace.append(_gate(Gate.G1_POLICY, Outcome.PASS, coverage_note))
        self._left["off_limits"] = coverage.off_limits(self._broker)
        self._left["unreadable"] = len(self._store.uncounted()) + unread

        self._step(3)
        query = build_query(question, person, self.spellings)
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
            linked = self._link(query, items, candidates)
            self._seen = (query, linked)
            known = {c.item.item_id for c in candidates}
            by_id = {i.item_id: i for i in items}
            candidates += [Candidate(by_id[i], 0.0) for i in linked if i not in known]
            second = False
            if not candidates:
                candidates, second = self._wider(query, items, []), True

            def read_note() -> str:
                return (
                    f"searched {len(items)} items; {len(self._store.uncounted()) + unread} "
                    f"could not be read; {len(candidates)} passed the relevance rule"
                    + ("; a second, wider search was made" if second else "")
                )

            if not candidates:
                trace.append(_gate(Gate.G2_READ, Outcome.PASS, read_note()))
                trace.append(_gate(Gate.G3_MODEL, Outcome.SKIPPED, "no note to show: not asked"))
                trace.append(_gate(Gate.G4_ANSWER, Outcome.PASS, "nothing relevant: not found"))
                return self._answer(
                    AnswerKind.NOT_FOUND, question, NOT_FOUND, [], [], trace, started
                )

            given, points, result = self._attempt(question, query, candidates, linked)
            if not points and not second:
                # Nothing held up: look once more, by meaning, at notes the words missed.
                more = self._wider(query, items, candidates)
                if more:
                    second = True
                    self._step(3, "second, wider search")
                    again, points, result = self._attempt(question, query, more, linked)
                    candidates, given = candidates + more, given + again
            trace.append(_gate(Gate.G2_READ, Outcome.PASS, read_note()))
            sure = [p for p in points if not p.related]  # the summary rests on these only
            summary = summarise(question, sure, self._model) if sure else ()
            self._step(5)
        except DeskThreadError as err:
            if self._stop.is_set():
                raise _StoppedError from err  # the request was cut off on purpose
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
        self._left.update(left_out(result))
        self.items_given += len(given)
        for g in given:
            self.given_by[g.item.source_id] = self.given_by.get(g.item.source_id, 0) + 1
        kind = AnswerKind.BRIEF if points else AnswerKind.NOT_FOUND
        message = "" if points else NOT_FOUND
        answer = self._answer(kind, question, message, points, given, trace, started, query)
        answer = answer.model_copy(update={"summary": summary})
        # A status only means something for things promised or to do.
        commitment = person is not None or bool(COMMITMENT_WORDS & set(stems(question)))
        return answer.model_copy(update={"show_status": commitment})

    # ------------------------------------------------------------------ one try, and a wider one
    def _attempt(
        self,
        question: str,
        query: Query,
        candidates: list[Candidate],
        linked: dict[str, tuple[str, str]],
    ) -> tuple[list[Given], list[Checked], GateResult]:
        """Show these notes to the AI, then check what it says."""
        given = self._give(candidates)
        self._step(4)
        if query.people:
            name = ", ".join(sorted(names_in(question))) or "the person asked about"
            kind = prompts.KIND_PERSON.format(name=name)
        elif query.window is not None:
            period = query.window_name + (" (only what is still ahead)" if query.forward else "")
            kind = prompts.KIND_PERIOD.format(period=period)
        else:
            kind = prompts.KIND_TOPIC
        prompt = prompts.ANSWER.format(
            question=question,
            notes=_render(given, linked),
            today=now().astimezone().strftime("%A %d %B %Y"),
            kind=kind,
        )
        proposed = parse_points(complete_json(self._model, prompt))
        self._step(5)
        points, result = check(query, proposed, given, self._model, linked, self._dropped)
        self._step(5)  # a question stopped while the AI was answering ends here
        return given, points, result

    def _wider(self, query: Query, items: list[Item], have: list[Candidate]) -> list[Candidate]:
        """A second look when the first found nothing: the notes closest in meaning to the
        question, below the usual bar. For a question about a person only notes that name
        the person. Empty when meaning search is off."""
        vectors = self._meaning.of_items(items)
        asked = self._meaning.of_text(query.question) if vectors else None
        if not vectors or asked is None:
            return []
        seen = {c.item.item_id for c in have}
        scored = [
            (likeness(vectors[i.item_id], asked), i)
            for i in items
            if i.item_id in vectors
            and i.item_id not in seen
            and i.kind is not ItemKind.EVENT
            and (not query.people or query.people & item_stems(i))
        ]
        scored.sort(key=lambda pair: (-pair[0], pair[1].item_id))
        return [Candidate(i, score) for score, i in scored[:8] if score >= config.LIKE_WIDER]

    def begin_preparing(self) -> None:
        """A picture job is about to start: from now on `preparing` says so."""
        with self._prep_lock:
            self._prep_jobs += 1
            if not self.preparing.active:
                self.preparing = Preparing(active=True, what="Reading pictures")

    def read_pictures_now(self) -> None:
        """Read the text of the pictures that have no reading yet (macOS first, the AI only for
        pictures without text), and say how far it is in `preparing`. This is the work between
        switching Pictures on and the first question; the screen keeps the chat closed until
        it is done."""

        pictures = 0

        def show(done: int, total: int, phase: str) -> None:
            nonlocal pictures
            if phase == "text":
                pictures = max(pictures, total)
            what = "Reading pictures" if phase == "text" else "Looking at pictures without text"
            self.preparing = Preparing(active=True, done=done, total=total, what=what)

        try:
            self._images.read_pending(show, None, use_model=True)
        finally:
            with self._prep_lock:
                self._prep_jobs = max(0, self._prep_jobs - 1)
                if self._prep_jobs == 0:
                    # macOS reads a picture in a tenth of a second, so the whole job can be
                    # over before anyone looks: "ready" stays visible for a few seconds.
                    self._ready_until = time.monotonic() + READY_SECONDS
                    self.preparing = (
                        Preparing(
                            active=False, done=pictures, total=pictures, what="Pictures ready"
                        )
                        if pictures
                        else Preparing()
                    )

    def preparing_now(self) -> Preparing:
        """What the screen shows: the running job, or "Pictures ready" for a few seconds."""
        with self._prep_lock:
            if not self.preparing.active and time.monotonic() > self._ready_until:
                self.preparing = Preparing()
            return self.preparing

    # ------------------------------------------------------------ the items behind the numbers
    def _details(self, answer: Answer) -> dict[str, object]:
        """The items of each stage of "how this was checked", so that every number can be
        opened: all that was read, what looked related and how, the quotes that were dropped,
        what could not be read, the files kept out of reach, the notes with instructions."""
        labels = {s.source_id: s.label for s in self._broker.states()}

        def ref(item: Item) -> ItemRef:
            return ItemRef(
                item_id=item.item_id,
                title=item.title,
                source_label=labels.get(item.source_id, item.source_id),
                kind=item.kind.value,
                date=item.date,
            )

        items = self._store.items()
        given = set(answer.given_item_ids)
        query, linked = self._seen if self._seen else (None, {})
        why = {
            ErrorCode.UNSUPPORTED_TYPE.value: "Format not supported",
            ErrorCode.READ_FAILED.value: "The file could not be opened",
        }
        unread = [
            Unread(location=u.location, why=why.get(u.reason, "Could not be read"))
            for u in self._store.uncounted()
        ] + [
            Unread(location=i.location, why="Picture not read: the AI in use could not read it")
            for i in items
            if i.kind is ItemKind.IMAGE and i.meta.get("reading") == "pending"
        ]
        return {
            "read_items": tuple(ref(i) for i in items),
            "related_items": tuple(
                RelatedRef(item=ref(i), how=_how(query, i, linked))
                for i in items
                if i.item_id in given
            ),
            "dropped_quotes": tuple(
                DroppedQuote(item=ref(item), quote=unit.text, why=reason)
                for item, unit, reason in self._dropped
            ),
            "unread": tuple(unread),
            "off_limits_names": tuple(coverage.off_limit_names(self._broker)),
            "instruction_notes": tuple(
                ref(i) for i in items if i.item_id in given and instruction_units(i)
            ),
        }

    # ------------------------------------------------------------------ related notes
    def _link(
        self, query: Query, items: list[Item], candidates: list[Candidate]
    ) -> dict[str, tuple[str, str]]:
        """Notes worth showing although the words of the question are not in them:
        item id -> (kind, plain reason).

        - "time": the question names a person, and the note was written around a calendar
          entry with that person.
        - "meaning": the note reads like the question (a question about a topic), or like
          the notes that do name the person (a question about a person).
        Calendar entries and reminders are not brought in this way: they are short and
        would match almost anything.
        """
        have = {c.item.item_id for c in candidates}
        loose = (ItemKind.NOTE, ItemKind.DOCUMENT, ItemKind.CHAT, ItemKind.IMAGE, ItemKind.MAIL)
        pool = [i for i in items if i.units and i.kind in loose and i.item_id not in have]
        linked: dict[str, tuple[str, str]] = {}
        name = ", ".join(sorted(names_in(query.question))) or "that person"

        if query.people:
            # Never a note about somebody else: anyone who appears in a calendar entry and
            # is not the person asked about rules a note out.
            others = {
                stem(word)
                for event in items
                if event.kind is ItemKind.EVENT
                for word in stems(event.meta.get("attendees", "") + " " + event.title)
                if word[:1].isalpha() and len(word) > 2
            } & {stem(n.lower()) for i in items for n in names_in(i.title)}
            others -= query.people
            pool = [
                i for i in pool if not query.people & item_stems(i) and not others & item_stems(i)
            ]
            for event in items:
                if event.kind is not ItemKind.EVENT or event.date is None:
                    continue
                if not query.people & item_stems(event):
                    continue
                start = _aware(event.date) - timedelta(minutes=15)
                try:
                    ends = datetime.fromisoformat(event.meta.get("end", ""))
                except ValueError:
                    ends = event.date + timedelta(hours=1)
                end = _aware(ends) + timedelta(minutes=45)
                for item in pool:
                    if item.date is not None and start <= _aware(item.date) <= end:
                        linked.setdefault(
                            item.item_id,
                            ("time", f"{name} is not named. Written around “{event.title}”."),
                        )

        vectors = self._meaning.of_items(items)
        if vectors:
            scores: list[tuple[float, Item]] = []
            if query.people:
                seeds = [
                    vectors[c.item.item_id] for c in candidates[:8] if c.item.item_id in vectors
                ]
                for item in pool:
                    if seeds and item.item_id in vectors and item.item_id not in linked:
                        best = max(likeness(vectors[item.item_id], seed) for seed in seeds)
                        if best >= config.LIKE_NOTES:
                            scores.append((best, item))
                why = f"{name} is not named. It reads like your notes about {name}."
            elif query.window is None:
                asked = self._meaning.of_text(query.question)
                for item in pool:
                    if asked and item.item_id in vectors:
                        best = likeness(vectors[item.item_id], asked)
                        if best >= config.LIKE_QUESTION:
                            scores.append((best, item))
                why = "It does not use the words of your question, but says something close."
            else:
                why = ""
            scores.sort(key=lambda pair: (-pair[0], pair[1].item_id))
            for _, item in scores[: config.RELATED_MAX]:
                linked[item.item_id] = ("meaning", why)
        return linked

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
        query: Query | None = None,
    ) -> Answer:
        labels = {s.source_id: s.label for s in self._broker.states()}
        brief = tuple(
            BriefPoint(
                label=p.label,
                status=PointStatus(p.status),
                note=p.note,
                related=p.related,
                why=p.why,
                matched=matched_words(query, p.cites) if query else (),
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


_TEAM_LIST = re.compile(r"^[A-Z][a-z]+(?:(?:,\s*|\s+and\s+)[A-Z][a-z]+)+\.?$")


def _attendees(item: Item) -> list[str]:
    """The people of a calendar entry: its attendees, and the names of an entry whose own
    notes are just a list of names ("Sam, Alex, Jo and Lee."). Nothing is guessed from text."""
    people = [p.strip() for p in item.meta.get("attendees", "").split(",") if p.strip()]
    for unit in item.units[1:]:
        body = unit.text[6:].strip() if unit.text.startswith("Notes:") else ""
        if _TEAM_LIST.match(body):
            people += [n for n in re.split(r",\s*|\s+and\s+", body.rstrip(".")) if n]
    return list(dict.fromkeys(people))


def _how(query: Query | None, item: Item, linked: dict[str, tuple[str, str]]) -> str:
    """Why an item looked related, in plain words."""
    if item.item_id in linked:
        return linked[item.item_id][1]
    if query is None:
        return "Found by its words"
    have = set(item_stems(item))
    words = [w for w in query.focus_words if stem(w) in have]
    names = sorted(n for n in names_in(query.question) if stem(n.lower()) in have)
    found = [*names, *[w for w in words if w not in names]]
    if found:
        return "Mentions " + ", ".join(found)
    if query.window is not None:
        return f"Dated {query.window_name}"
    return "Found by its words"


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.astimezone()


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


def _render(given: list[Given], linked: dict[str, tuple[str, str]] | None = None) -> str:
    """The notes as the model sees them: alias, kind, date, title, numbered lines. A note
    that was brought in without naming the person is marked "related"."""
    blocks = []
    for g in given:
        head = f"[{g.alias}] {g.item.kind.value} | {_when(g.item.date)} | {g.item.title}"
        if linked and g.item.item_id in linked:
            head += " | related"
        lines = [
            f"{u.number}. {prompts.WITHHELD if u.number in g.withheld else u.text}"
            for u in g.item.units
        ]
        blocks.append("\n".join([head, *lines]))
    return "\n\n".join(blocks)
