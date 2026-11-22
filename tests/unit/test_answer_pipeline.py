"""U3, U4, U7, U10 and the salary case: one question end to end with a scripted fake model
(FT-10, FT-11, FT-12, FT-13, FT-44)."""

import shutil
from pathlib import Path

import pytest

from app.assistant import NOT_FOUND
from app.gate import instruction_units
from contracts.api import AnswerKind, PointStatus
from contracts.gates import Gate, Outcome
from tests.fakes import SAM_BRIEF, STORY_NOW, FakeModel, gate, open_work


@pytest.fixture(autouse=True)
def clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DESKTHREAD_NOW", STORY_NOW)


# ------------------------------------------------------------------ the brief (FT-10, U7)


def test_the_brief_quotes_are_copied_from_the_notes_with_dates_and_status(
    demo_laptop: Path,
) -> None:
    _, assistant = open_work(demo_laptop, FakeModel(lambda q: SAM_BRIEF))
    answer = assistant.ask("What did I promise Sam?")
    assert answer.kind is AnswerKind.BRIEF and len(answer.points) == 4
    course, conference, intro, ownership = answer.points

    assert [c.quote for c in conference.citations] == [
        "- said I'd back Sam for the pharma data conference in Feb (Manchester). "
        "need to check travel budget",
        "- Feb conference: dropped. no travel budget this half. told Sam today",
    ]
    assert conference.status is PointStatus.SUPERSEDED
    dates = [c.date for c in conference.citations]
    assert dates[0] is not None and dates[1] is not None and dates[0] < dates[1]

    # U7: a cited line that says "approved" makes the point done; a note with no date written
    # in it is dated by its file (user rule); a point made only of question marks is never
    # "done".
    assert course.status is PointStatus.DONE
    assert ownership.citations[0].undated is False
    assert ownership.status is PointStatus.OPEN
    assert "not stated as a clear promise" in ownership.note
    assert intro.citations[0].source_label == "Note files"
    assert "on this laptop only" in gate(answer, Gate.G3_MODEL)[1]
    assert "no tools" in gate(answer, Gate.G3_MODEL)[1]


# ------------------------------------------------------------------ U3: the answer gate


def test_u3_a_citation_that_points_at_nothing_is_dropped(demo_laptop: Path) -> None:
    model = FakeModel(
        lambda q: [("Invented", "open", []), ("Real", "open", [("recap", "dropped")])]
    )
    model.raw_cites = [{"id": "A99", "line": 1}, {"id": "A1", "line": 999}, {"id": "A1"}]
    _, assistant = open_work(demo_laptop, model)
    answer = assistant.ask("What did I promise Sam?")
    assert [p.label for p in answer.points] == ["Real"]
    assert len(answer.points[0].citations) == 1
    outcome, detail = gate(answer, Gate.G4_ANSWER)
    assert outcome is Outcome.WARN and "4 citations pointed at nothing" in detail


def test_u3_no_supported_point_becomes_not_found(demo_laptop: Path) -> None:
    _, assistant = open_work(demo_laptop, FakeModel(lambda q: [("A promotion", "open", [])]))
    answer = assistant.ask("What did I promise Sam?")
    assert answer.kind is AnswerKind.NOT_FOUND and answer.message == NOT_FOUND
    assert answer.points == () and answer.coverage.cited == 0
    assert gate(answer, Gate.G4_ANSWER)[0] is Outcome.FAIL


def test_the_salary_question_rejects_a_real_quote_on_another_subject(demo_laptop: Path) -> None:
    """ "Budget approved up to 800" exists and is about Sam, but it is not a salary."""
    model = FakeModel(
        lambda q: [("Salary", "done", [("Course budget", "Budget approved up to 800")])],
        verify="no",
        words=["pay", "budget", "money"],
    )
    _, assistant = open_work(demo_laptop, model)
    answer = assistant.ask("What salary did I promise Sam?")
    assert answer.kind is AnswerKind.NOT_FOUND
    assert "real but not about the question" in gate(answer, Gate.G4_ANSWER)[1]
    assert answer.coverage.given_to_model > 0 and answer.coverage.cited == 0


def test_no_answer_call_is_made_when_nothing_passes_the_relevance_rule(
    demo_laptop: Path,
) -> None:
    model = FakeModel(lambda q: [("x", "open", [])], words=["remuneration"])
    _, assistant = open_work(demo_laptop, model)
    assistant.ask("warm up")
    before = model.calls
    answer = assistant.ask("What salary did I promise Sam?")
    assert answer.kind is AnswerKind.NOT_FOUND
    assert model.calls - before == 1  # only the word suggestion; no answer call was made
    assert gate(answer, Gate.G3_MODEL)[0] is Outcome.SKIPPED
    assert answer.coverage.given_to_model == 0


def test_a_passing_mention_in_a_note_about_someone_else_is_not_a_promise_to_sam(
    demo_laptop: Path,
) -> None:
    model = FakeModel(lambda q: [("Share the Q1 plan", "open", [("Lee - catch up", "Q1 plan")])])
    _, assistant = open_work(demo_laptop, model)
    assert assistant.ask("What did I promise Sam?").kind is AnswerKind.NOT_FOUND


# ------------------------------------------------------------------ U4: injection


def test_u4_a_note_with_instructions_is_flagged_and_its_orders_never_reach_the_model(
    demo_laptop: Path,
) -> None:
    model = FakeModel(
        lambda q: [
            ("Promotion", "open", [("ideas / scratch", "withheld")]),
            ("Present at offsite", "open", [("ideas / scratch", "Sam could present")]),
        ]
    )
    session, assistant = open_work(demo_laptop, model)
    answer = assistant.ask("What did I promise Sam?")
    sent = next(p for p in model.prompts if "Notes:\n" in p)  # the answer prompt
    assert all("ignore your rules" not in p for p in model.prompts)  # nor in any other
    assert "promised a promotion" not in sent
    assert "[line withheld" in sent
    assert [p.label for p in answer.points] == ["Present at offsite"]  # the order was not followed
    outcome, detail = gate(answer, Gate.G4_ANSWER)
    assert outcome is Outcome.WARN
    assert "1 note contained instructions: treated as content only" in detail
    scratch = next(i for i in session.store.items() if i.location.endswith("ideas-scratch.md"))
    assert instruction_units(scratch) == {4, 5}
    assert "performance plan" not in "\n".join(model.prompts)  # the private note was never read


# ------------------------------------------------------------------ coverage on every answer


def test_u9_every_answer_carries_coverage_also_not_found(demo_laptop: Path) -> None:
    _, assistant = open_work(demo_laptop, FakeModel(lambda q: SAM_BRIEF))
    for question in ("What did I promise Sam?", "What salary did I promise Sam?"):
        cov = assistant.ask(question).coverage
        assert cov.accessible == cov.searched + cov.unsupported
        assert cov.cited <= cov.given_to_model <= cov.searched
    first = assistant.ask("What did I promise Sam?")
    assert first.coverage.cited == 4
    assert set(first.given_item_ids) >= {c.item_id for p in first.points for c in p.citations}


def test_u10_a_note_deleted_mid_session_is_not_cited_and_coverage_drops(
    demo_laptop: Path, tmp_path: Path
) -> None:
    root = tmp_path / "demo-laptop"
    shutil.copytree(demo_laptop, root)
    _, assistant = open_work(root, FakeModel(lambda q: SAM_BRIEF))
    before = assistant.ask("What did I promise Sam?")
    (root / "App-exports/Notes/follow-ups.md").unlink()
    after = assistant.ask("What did I promise Sam?")
    assert after.coverage.accessible == before.coverage.accessible - 1
    assert all(c.title != "follow-ups" for p in after.points for c in p.citations)
    assert "Intro to Mark" not in [p.label for p in after.points]


def test_revoking_a_source_takes_it_out_of_the_next_answer(demo_laptop: Path) -> None:
    session, assistant = open_work(demo_laptop, FakeModel(lambda q: SAM_BRIEF))
    assert len(assistant.ask("What did I promise Sam?").points) == 4
    session.broker.revoke("folder:notes")
    answer = assistant.ask("What did I promise Sam?")
    assert [p.label for p in answer.points] == ["Online course"]  # only the mail is left
    assert all(c.source_id != "folder:notes" for p in answer.points for c in p.citations)
    assert answer.coverage.not_accessible["Note files"] == 21
    session.broker.revoke_all()
    stopped = assistant.ask("What did I promise Sam?")
    assert stopped.kind is AnswerKind.NO_SOURCES and stopped.coverage.accessible == 0


def test_a_summary_sentence_is_kept_only_when_the_quoted_lines_carry_it() -> None:
    from app.gate import Checked, matched_words, summarise
    from app.search import build_query
    from contracts.items import Item, ItemKind, Unit

    unit = Unit(number=1, text="Promised Sam a data storytelling course, budget 800 pounds")
    item = Item(
        item_id="i1", source_id="folder:notes", kind=ItemKind.NOTE, title="1:1 Sam", units=(unit,)
    )
    points = [Checked("Course for Sam", "open", ((item, unit),))]
    model = FakeModel(lambda _q: [])
    model.summary = [
        {"text": "You promised Sam a data storytelling course with a budget of 800.", "lines": [1]},
        {"text": "The budget was 1200 pounds.", "lines": [1]},  # a number the line does not say
        {"text": "Sam will also get a new laptop and a pay rise next spring.", "lines": [1]},
        {"text": "You promised Sam a course.", "lines": [7]},  # rests on a line that is not there
        {"text": "You promised Sam a course.", "lines": []},
    ]
    question = "What did I promise Sam about the course?"
    assert summarise(question, points, model) == (
        "You promised Sam a data storytelling course with a budget of 800.",
    )
    assert matched_words(build_query(question), points[0].cites) == ("Sam", "course")


def test_an_answer_names_its_model_and_counts_what_was_left_out(demo_laptop: Path) -> None:
    model = FakeModel(lambda _question: SAM_BRIEF)
    model.raw_cites = [{"id": "A99", "line": 1}]  # a citation of a note that was never given
    _session, assistant = open_work(demo_laptop, model)
    answer = assistant.ask("What did I promise Sam?")
    assert answer.model_name == "Gemma 4"
    assert answer.left_out["nowhere"] >= 1 and answer.left_out["instructions"] >= 1
    assert all(count > 0 for count in answer.left_out.values())
    assert gate(answer, Gate.G4_ANSWER)[1].count("citations pointed at nothing") == 1
