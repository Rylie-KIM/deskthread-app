"""End session and the receipt (FT-16, FT-40)."""

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.model import ModelGateway, ModelServer
from app.runtime import Runtime
from contracts.api import ROUTES, TOKEN_HEADER
from tests.conftest import CANARY
from tests.fakes import SAM_BRIEF, STORY_NOW, FakeModel

PORT = 8765


class FakeGateway(ModelGateway):
    def __init__(self) -> None:
        super().__init__()
        self.is_loaded = True

    def loaded(self) -> bool:
        return self.is_loaded

    def unload(self, wait_s: float = 20) -> bool:
        self.is_loaded = False
        return True


class FakeServer(ModelServer):
    def __init__(self) -> None:
        super().__init__()
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


@pytest.fixture(autouse=True)
def clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DESKTHREAD_NOW", STORY_NOW)


def _started(root: Path) -> tuple[TestClient, Runtime, list[str]]:
    runtime = Runtime(
        FakeModel(lambda q: SAM_BRIEF), PORT, gateway=FakeGateway(), server=FakeServer()
    )
    events: list[str] = []
    runtime.stop = lambda: events.append("backend stopped")
    client = TestClient(
        create_app(runtime),
        base_url=f"http://127.0.0.1:{PORT}",
        headers={TOKEN_HEADER: runtime.token},
    )
    client.post("/api/folder", json={"path": str(root)})
    for source in ("folder:notes", "folder:mail"):
        client.post(f"/api/sources/{source}/grant", json={})
    return client, runtime, events


def test_end_session_clears_everything_and_stops_the_programs(demo_laptop: Path) -> None:
    client, runtime, events = _started(demo_laptop)
    client.post("/api/ask", json={"question": "What did I promise Sam?"})
    receipt = client.post("/api/end-session").json()
    assert receipt["questions"] == 1 and receipt["items_given_to_model"] > 0
    assert receipt["items_read"] >= 33  # the grants, and the read again for the question
    assert receipt["memory_cleared"] is True and receipt["model_unloaded"] is True
    assert receipt["all_connections_local"] is True
    assert receipt["folders"][0]["unchanged"] is True
    assert "cannot prove that memory was erased" in receipt["limits"]

    assert runtime.session is not None and runtime.session.store.items() == []
    assert all(s.status.value != "on" for s in runtime.session.broker.states())
    assert isinstance(runtime.server, FakeServer) and runtime.server.stopped
    assert events == ["backend stopped"]  # after the receipt was sent


def test_the_receipt_holds_counts_only_never_note_text(demo_laptop: Path, tmp_path: Path) -> None:
    root = tmp_path / "demo-laptop"
    shutil.copytree(demo_laptop, root)
    note = root / "App-exports" / "Notes" / "follow-ups.md"
    note.write_text(note.read_text() + f"- ref {CANARY}\n")
    client, _, _ = _started(root)
    client.post("/api/ask", json={"question": "What did I promise Sam?"})
    text = client.post("/api/end-session").text
    assert CANARY not in text and "conference" not in text and "follow-ups" not in text


def test_ending_before_a_folder_is_chosen_still_works() -> None:
    runtime = Runtime(FakeModel(lambda q: []), PORT)
    client = TestClient(
        create_app(runtime),
        base_url=f"http://127.0.0.1:{PORT}",
        headers={TOKEN_HEADER: runtime.token},
    )
    receipt = client.post("/api/end-session").json()
    assert receipt["questions"] == 0 and receipt["memory_cleared"] is True


def test_the_api_now_serves_every_route_of_the_contract() -> None:
    from fastapi.routing import APIRoute

    served = {
        f"{method} {route.path}"
        for route in create_app(Runtime(FakeModel(lambda q: []), PORT)).routes
        if isinstance(route, APIRoute)
        for method in (route.methods or set()) - {"HEAD", "OPTIONS"}
    }
    assert served == set(ROUTES)
