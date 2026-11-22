"""Gate G4, the answer check (FT-12, FT-13, FT-11).

The model proposes points as (note id, line number). Here, in code:
1. every citation must name a note that was given and a line that exists, else it is dropped;
2. the quote is taken from that line, so it is verbatim by construction;
3. the cited line must be relevant: it must share the person and the topic of the question,
   and (for questions with a topic) pass a second yes/no check by the model;
4. lines that read like instructions to an assistant are withheld from the model before it
   answers, and can never be cited;
5. a point with no citation left is dropped; no point left means "not found".
It proves a quote exists and is on the subject. It cannot prove the quote means what the
manager meant; that limit is stated in the README.
"""

import re
from dataclasses import dataclass

from app import prompts
from app.model import Model, complete_json
from app.search import Query, stems
from contracts.errors import DeskThreadError
from contracts.gates import Gate, GateResult, Outcome, ProposedCitation, ProposedPoint
from contracts.items import Item, Unit

INSTRUCTION = re.compile(
    r"ignore (?:all |any |your |the |previous |prior )*(?:rules|instructions|prompt)"
    r"|disregard (?:all |your |the |previous )*(?:rules|instructions)"
    r"|system (?:note|prompt|message)|to any ai|ai assistant|you are now|you must now"
    r"|print every note|reveal (?:your|the) (?:prompt|instructions)|include the private",
    re.I,
)
DONE = re.compile(r"\bapproved\b|\[done\]|\bcompleted\b|\bsigned off\b", re.I)
STATUSES = frozenset({"done", "open", "changed", "superseded"})
UNCLEAR = "Written as a question or a maybe: not stated as a clear promise."


def instruction_units(item: Item) -> set[int]:
    """Numbers of the lines that try to give an assistant orders. A list item that starts
    such a line and the lines that continue it are taken together."""
    flagged: set[int] = set()
    for unit in item.units:
        if INSTRUCTION.search(unit.text):
            flagged.add(unit.number)
            nxt = item.unit(unit.number + 1)
            if nxt is not None and not nxt.text.lstrip().startswith(("-", "*", "#")):
                flagged.add(nxt.number)
    return flagged


@dataclass(frozen=True)
class Given:
    """A note as handed to the model: under a short alias, with some lines withheld."""

    alias: str
    item: Item
    withheld: frozenset[int]


def parse_points(data: dict[str, object]) -> list[ProposedPoint]:
    """The model's JSON to typed points. Anything malformed is skipped, never trusted."""
    points: list[ProposedPoint] = []
    raw = data.get("points", [])
    for entry in raw if isinstance(raw, list) else []:
        if not isinstance(entry, dict):
            continue
        cites: list[ProposedCitation] = []
        raw_cites = entry.get("cites", [])
        for cite in raw_cites if isinstance(raw_cites, list) else []:
            if isinstance(cite, dict) and isinstance(cite.get("line"), int):
                cites.append(ProposedCitation(item_id=str(cite.get("id", "")), unit=cite["line"]))
        status = str(entry.get("status", "open")).lower()
        points.append(
            ProposedPoint(
                label=str(entry.get("label", "")).strip()[:80] or "Point",
                status=status if status in STATUSES else "open",
                citations=tuple(cites),
            )
        )
    return points


@dataclass(frozen=True)
class Checked:
    label: str
    status: str
    cites: tuple[tuple[Item, Unit], ...]
    note: str = ""


def _on_person(query: Query, item: Item, unit: Unit) -> bool:
    """Is this line about the person asked about? The line itself must name the person, or
    the note's heading must (title, attendees, or a top line that is not a list entry).
    A passing mention further down a note about someone else does not count."""
    if not query.people:
        return True
    heading = [u.text for u in item.units[:3] if not u.text.lstrip().startswith(("-", "*"))]
    text = " ".join([item.title, item.meta.get("attendees", ""), unit.text, *heading])
    return bool(query.people & set(stems(text)))


def check(
    query: Query, proposed: list[ProposedPoint], given: list[Given], model: Model | None
) -> tuple[list[Checked], GateResult]:
    by_alias = {g.alias: g for g in given}
    invalid = off_topic = 0
    kept: list[Checked] = []
    for point in proposed:
        cites: list[tuple[Item, Unit]] = []
        for cite in point.citations:
            entry = by_alias.get(cite.item_id)
            unit = entry.item.unit(cite.unit) if entry else None
            if entry is None or unit is None or cite.unit in entry.withheld:
                invalid += 1  # a note that was not given, a line that does not exist
                continue
            if not _on_person(query, entry.item, unit):
                off_topic += 1
                continue
            if (entry.item, unit) not in cites:
                cites.append((entry.item, unit))
        if cites:
            kept.append(Checked(point.label, point.status, tuple(cites)))

    # Second look for questions with a topic: is each quoted line really on that topic?
    if kept and query.focus and model is not None:
        flat = [(p, c) for p, checked in enumerate(kept) for c in checked.cites]
        quotes = "\n".join(
            f'{n}. (from the note "{c[0].title}") {c[1].text}' for n, (_, c) in enumerate(flat, 1)
        )
        prompt = prompts.VERIFY.format(
            question=query.question, focus=", ".join(query.focus_words), quotes=quotes
        )
        try:
            answers = complete_json(model, prompt).get("answers", [])
        except DeskThreadError:
            answers = []
        verdicts = [str(a).strip().lower().startswith("y") for a in answers]
        if len(verdicts) != len(flat):
            verdicts = [False] * len(flat)  # an unusable check supports nothing
        survivors: list[Checked] = []
        for p, checked in enumerate(kept):
            good = [c for (index, c), ok in zip(flat, verdicts, strict=True) if index == p and ok]
            off_topic += len(checked.cites) - len(good)
            if good:
                survivors.append(Checked(checked.label, checked.status, tuple(good)))
        kept = survivors

    kept = [_tidy(point) for point in kept]
    flagged = sum(1 for g in given if g.withheld)
    parts = [f"{len(kept)} of {len(proposed)} points kept"]
    if invalid:
        parts.append(f"{invalid} citations pointed at nothing and were dropped")
    if off_topic:
        parts.append(f"{off_topic} quotes were real but not about the question and were dropped")
    if flagged:
        parts.append(f"{flagged} note contained instructions: treated as content only")
    parts.append("every quote copied from its note by code")
    outcome = Outcome.PASS if kept and not (invalid or off_topic or flagged) else Outcome.WARN
    if not kept:
        outcome = Outcome.FAIL if proposed else Outcome.PASS
        parts[0] = "nothing in the notes supports an answer" if proposed else "no answer proposed"
    return kept, GateResult(gate=Gate.G4_ANSWER, outcome=outcome, detail="; ".join(parts))


def _tidy(point: Checked) -> Checked:
    """Messy-note handling (FT-11): order by date and say when a point is only a maybe."""
    cites = sorted(
        point.cites, key=lambda c: (c[0].date is None, c[0].date.timestamp() if c[0].date else 0)
    )
    unclear = all("?" in unit.text for _, unit in cites)
    status = point.status
    if status == "open" and any(DONE.search(unit.text) for _, unit in cites):
        status = "done"  # a cited line says so in plain words
    if unclear and status == "done":
        status = "open"
    return Checked(point.label, status, tuple(cites), UNCLEAR if unclear else "")
