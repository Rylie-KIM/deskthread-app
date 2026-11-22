"""Candidate selection with no stored index (FT-08): the floor, names, the relevance rule."""

from pathlib import Path

from app.broker import Broker
from app.policy import AccessPolicy
from app.search import add_expansion, build_query, find, keyword_floor, names_in, stem
from app.sources.folder import scan
from app.store import SessionStore
from contracts.items import Item, ItemKind


def _items(root: Path) -> list[Item]:
    broker = Broker()
    for adapter in scan(root, AccessPolicy([root])):
        broker.register(adapter)
    store = SessionStore(broker)
    for state in broker.states():
        broker.grant(state.source_id, frozenset())
        store.load(state.source_id)
    return store.items()


def test_names_and_stems() -> None:
    assert names_in("What did I promise Sam?") == {"Sam"}
    assert names_in("Did HR approve the money for Sam's course?") == {"HR", "Sam"}
    assert stem("promised") == stem("promise") and stem("courses") == stem("course")
    query = build_query("What salary did I promise Sam?")
    assert query.focus == {stem("salary")} and query.people == {"sam"}
    assert build_query("What did I promise Sam?").focus == set()
    assert build_query("What did I promise Sam, and where does each thing stand?").focus == set()


def test_d1_an_ordinary_search_for_the_managers_words_finds_nothing(demo_laptop: Path) -> None:
    items = _items(demo_laptop)
    assert keyword_floor("development goals", items) == []
    assert len(keyword_floor("conference in Feb", items)) >= 1


def test_a_question_about_a_person_finds_the_notes_written_in_other_words(
    demo_laptop: Path,
) -> None:
    found = find(build_query("What did I promise Sam?"), _items(demo_laptop))
    locations = {c.item.location for c in found}
    assert {
        "App-exports/Notes/follow-ups.md",
        "App-exports/Notes/1on1-sam-recap-nov.md",
        "App-exports/Notes/sam-fragment.md",
        "App-exports/Mail/2026-11-10_RE_Sam_course_budget.eml",
        "App-exports/Teams/2026-11-04_meeting-recap_career-chat-Sam.txt",
        "App-exports/Slack/saved-items.txt",
    } <= locations
    assert not any("alex-1on1" in loc for loc in locations)
    assert all(c.item.kind is not ItemKind.EVENT for c in found)  # who and when, not what
    assert [c.score for c in found] == sorted((c.score for c in found), reverse=True)


def test_the_relevance_rule_a_name_alone_is_not_enough_for_a_question_with_a_topic(
    demo_laptop: Path,
) -> None:
    items = _items(demo_laptop)
    query = build_query("What salary did I promise Sam?")
    assert find(query, items) == []  # nothing mentions a salary: no model call will be made
    add_expansion(query, ["pay", "wage"])
    assert find(query, items) == []  # the pay-cycle mail is not about Sam
    add_expansion(query, ["budget"])
    found = {c.item.location for c in find(query, items)}
    assert "App-exports/Mail/2026-11-10_RE_Sam_course_budget.eml" in found  # left to the gate


def test_suggested_words_widen_the_search_but_weigh_less(demo_laptop: Path) -> None:
    items = _items(demo_laptop)
    query = build_query("What are the growth plans for Sam?")
    before = {c.item.location for c in find(query, items)}
    add_expansion(query, ["course", "career chat", "ownership"])
    after = {c.item.location for c in find(query, items)}
    assert before < after and "App-exports/Notes/sam-fragment.md" in after


def test_a_question_about_a_day_shows_what_is_dated_then_whatever_its_words() -> None:
    from datetime import UTC, datetime, timedelta

    from app.clock import now
    from app.search import time_window
    from contracts.items import Item, ItemKind, Unit

    today = now().astimezone().replace(hour=19, minute=0)

    def make(item_id: str, kind: ItemKind, title: str, date: datetime | None, **meta: str) -> Item:
        unit = Unit(number=1, text=title)
        return Item(item_id=item_id, source_id="mac:x", kind=kind, title=title, units=(unit,),
                    date=date, meta=meta)  # fmt: skip

    items = [
        make("film", ItemKind.EVENT, "Cinema booking", today),
        make("old", ItemKind.EVENT, "Dentist", today - timedelta(days=9)),
        make("next", ItemKind.EVENT, "Team offsite", today + timedelta(days=1)),
        make("milk", ItemKind.REMINDER, "Buy milk", None, status="open"),
        make("done", ItemKind.REMINDER, "Pay rent", None, status="done"),
        make("note", ItemKind.NOTE, "todo: call the bank about today", None),
    ]
    query = build_query("What is my todo for today?")
    assert query.focus == set() and query.window_name == "today"
    assert [c.item.item_id for c in find(query, items)] == ["milk", "film", "note"]
    assert [c.item.item_id for c in find(build_query("What is on tomorrow?"), items)] == ["next"]
    assert find(build_query("What did I promise Sam?"), items) == []  # no day named: as before
    fixed = datetime(2026, 11, 22, 23, 30, tzinfo=UTC)  # a Sunday
    start, end, name = time_window("anything next week?", fixed) or (None, None, "")
    assert name == "next week" and start is not None and end is not None
    assert (end - start).days == 6 and start.weekday() == 0


def test_other_spellings_of_a_name_count_as_the_same_person() -> None:
    from contracts.items import Item, ItemKind, Unit

    def note(item_id: str, text: str) -> Item:
        unit = Unit(number=1, text=text)
        return Item(item_id=item_id, source_id="x", kind=ItemKind.NOTE, title=text, units=(unit,))

    items = [
        note("long", "Samuel: course budget"),
        note("short", "Sam: course budget"),
        note("other", "Alex: laptop"),
    ]
    plain = build_query("What did I promise Sam?")
    assert [c.item.item_id for c in find(plain, items)] == ["short"]
    known = build_query("What did I promise Sam?", None, {"Sam": ("Samuel", "Sammy")})
    assert {c.item.item_id for c in find(known, items)} == {"long", "short"}
    asked_other_way = build_query("What did I promise Samuel?", None, {"Sam": ("Samuel",)})
    assert {c.item.item_id for c in find(asked_other_way, items)} == {"long", "short"}
