"""Image reading (FT-39): read by the model in memory, citable, cached, forgotten on request."""

from pathlib import Path

import pytest

from contracts.items import ItemKind
from tests.fakes import STORY_NOW, FakeModel, open_work

KEY_IMAGE = "Desktop/Screenshot 2026-11-13 at 09.41.22.png"


@pytest.fixture(autouse=True)
def clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DESKTHREAD_NOW", STORY_NOW)


def _model(demo_laptop: Path) -> FakeModel:
    model = FakeModel(
        lambda q: [("Stretch project", "open", [("Screenshot 2026-11-13", "stretch project")])]
    )
    model.image_text[(demo_laptop / KEY_IMAGE).read_bytes()] = (
        "Memo - Sam\nmore ownership?\nstretch project: lead the checklist"
    )
    return model


def test_a_typed_screenshot_is_read_and_can_be_cited(demo_laptop: Path) -> None:
    session, assistant = open_work(demo_laptop, _model(demo_laptop))
    answer = assistant.ask("What did I promise Sam?")
    cite = answer.points[0].citations[0]
    assert cite.quote == "stretch project: lead the checklist"
    assert cite.read_by_model is True and cite.source_label == "Pictures"
    images = [i for i in session.store.items() if i.kind is ItemKind.IMAGE]
    assert sorted(i.meta["reading"] for i in images) == ["done"] + ["no text found"] * 4


def test_an_image_is_read_once_per_session_and_forgotten_on_request(demo_laptop: Path) -> None:
    model = _model(demo_laptop)
    session, assistant = open_work(demo_laptop, model)
    assistant.ask("What did I promise Sam?")
    calls = model.calls
    assert assistant.readings_held == 5
    assistant.ask("What did I promise Sam?")
    assert model.calls == calls + 2  # the answer and its summary; no image read again
    assistant.forget()
    assert assistant.readings_held == 0 and session.store.items() == []


def test_an_image_in_a_revoked_source_is_never_sent_to_the_model(demo_laptop: Path) -> None:
    model = _model(demo_laptop)
    session, assistant = open_work(demo_laptop, model)
    session.broker.revoke("folder:images")
    answer = assistant.ask("What did I promise Sam?")
    assert assistant.readings_held == 0
    assert all("Transcribe" not in p for p in model.prompts)
    assert answer.points == ()


def test_pictures_are_read_by_macos_when_switched_on_and_the_ai_only_fills_the_gaps(
    demo_laptop: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("Vision")
    monkeypatch.delenv("DESKTHREAD_OCR", raising=False)
    model = _model(demo_laptop)
    session, assistant = open_work(demo_laptop, model)
    calls = model.calls
    shown: list[str] = []
    original = assistant._images.read_pending

    def watching(progress=None, check=None, use_model=True):  # type: ignore[no-untyped-def]
        def note(done: int, total: int, phase: str) -> None:
            shown.append(f"{phase} {done} of {total}")

        return original(note, check, use_model)

    assistant._images.read_pending = watching  # type: ignore[method-assign]
    session.store.refresh()  # the sources are read when they are switched on
    assistant.begin_preparing()
    assistant.read_pictures_now()  # then the pictures are read, before the first question
    assert model.calls == calls + 2  # the AI looked only at the two pictures without text
    images = {i.title: i for i in session.store.items() if i.kind is ItemKind.IMAGE}
    typed = [i for i in images.values() if i.meta["reading"] == "done"]
    assert len(typed) == 3
    assert shown == [f"text {n} of 5" for n in range(1, 6)] + ["look 1 of 2", "look 2 of 2"]
    assert all(i.meta["read_with"] == "macOS text recognition" and i.read_by_model for i in typed)
    assert any("stretch project" in u.text for i in typed for u in i.units)
    assert sorted(i.meta["reading"] for i in images.values()) == [
        "done", "done", "done", "no text found", "no text found"
    ]  # fmt: skip
    before = model.calls
    assistant.ask("What did I promise Sam?")  # the first question has no picture left to read
    assert all("Transcribe" not in p for p in model.prompts[before:])
