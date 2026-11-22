"""Prepare my next meeting (FT-34): the work calendar names the person; personal stays out."""

from pathlib import Path

import pytest

from contracts.api import AnswerKind
from tests.fakes import SAM_BRIEF, STORY_NOW, FakeModel, open_work


@pytest.fixture(autouse=True)
def clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DESKTHREAD_NOW", STORY_NOW)


def test_tomorrows_one_to_one_comes_from_the_work_calendar_only(demo_laptop: Path) -> None:
    _, assistant = open_work(demo_laptop, FakeModel(lambda q: SAM_BRIEF))
    meetings = assistant.meetings()
    first = meetings[1]
    assert (first.title, first.person) == ("1:1 Sam", "Sam")
    assert (first.start.day, first.start.hour) == (23, 10)
    titles = [m.title for m in meetings]
    assert "Dentist" not in titles  # the personal calendar is Off in the Work profile
    assert titles == ["Team stand-up", "1:1 Sam", "1:1 Alex", "Coffee with Mark"]  # any entry
    assert [m.person for m in meetings] == ["", "Sam", "Alex", "Mark"]


def test_prepare_builds_the_brief_about_the_person_in_the_meeting(demo_laptop: Path) -> None:
    model = FakeModel(lambda q: SAM_BRIEF)
    _, assistant = open_work(demo_laptop, model)
    answer = assistant.prepare(assistant.meetings()[1].meeting_id)
    assert answer.kind is AnswerKind.BRIEF and answer.question == "What did I promise Sam?"
    assert answer.show_status is True  # a question about promises: statuses mean something
    assert all("other single words" not in p for p in model.prompts)  # no topic: no expansion
    team = assistant.prepare(assistant.meetings()[0].meeting_id)  # the stand-up has four people
    assert team.question == "What did I promise Sam, Alex, Jo and Lee?"
    assert team.show_status is True
    assert len(answer.points) == 4


def test_no_meeting_is_shown_when_the_calendar_is_off(demo_laptop: Path) -> None:
    session, assistant = open_work(demo_laptop, FakeModel(lambda q: SAM_BRIEF))
    session.broker.revoke("folder:calendar")
    assert assistant.meetings() == []


def test_an_entry_without_attendees_whose_notes_list_names_is_prepared_for_those_people() -> None:
    from app.assistant import _attendees
    from contracts.items import Item, ItemKind, Unit

    def entry(note: str, **meta: str) -> Item:
        lines = ["Weekly team meeting - Mon 23 Nov 2026 11:30", f"Notes: {note}"]
        return Item(source_id="x", item_id="e", kind=ItemKind.EVENT, title="Weekly team meeting",
                    units=tuple(Unit(number=i, text=t) for i, t in enumerate(lines, 1)),
                    meta=meta)  # fmt: skip

    assert _attendees(entry("Sam, Alex, Jo and Lee.")) == ["Sam", "Alex", "Jo", "Lee"]
    assert _attendees(entry("Monthly one-to-one with Sam.")) == []  # a sentence is not a list
    assert _attendees(entry("Daily standup.", attendees="Sam, Alex")) == ["Sam", "Alex"]
