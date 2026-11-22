"""The Memory panel and Forget now (FT-35, FT-37)."""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.model import ModelGateway
from app.proof.processes import BACKEND, watched
from app.runtime import Runtime
from contracts.api import TOKEN_HEADER
from tests.fakes import SAM_BRIEF, STORY_NOW, FakeModel

PORT = 8765


class FakeGateway(ModelGateway):
    """Stands in for the model runtime's loaded/unload calls."""

    def __init__(self) -> None:
        super().__init__()
        self.is_loaded = True
        self.unloads = 0

    def loaded(self) -> bool:
        return self.is_loaded

    def unload(self) -> bool:
        self.is_loaded = False
        self.unloads += 1
        return True


@pytest.fixture(autouse=True)
def clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DESKTHREAD_NOW", STORY_NOW)


@pytest.fixture
def runtime() -> Runtime:
    return Runtime(FakeModel(lambda q: SAM_BRIEF), PORT, gateway=FakeGateway())


@pytest.fixture
def client(runtime: Runtime, demo_laptop: Path) -> TestClient:
    client = TestClient(
        create_app(runtime),
        base_url=f"http://127.0.0.1:{PORT}",
        headers={TOKEN_HEADER: runtime.token},
    )
    client.post("/api/folder", json={"path": str(demo_laptop)})
    for source in ("folder:notes", "folder:mail", "folder:images"):
        client.post(f"/api/sources/{source}/grant", json={})
    return client


def test_the_panel_shows_what_is_held_right_now(client: TestClient) -> None:
    before = client.get("/api/memory").json()
    assert before["items_by_source"] == {"Note files": 21, "Mail files": 12, "Pictures": 5}
    assert before["items_held"] == 38 and before["image_readings_held"] == 0
    assert before["model_loaded"] is True
    client.post("/api/ask", json={"question": "What did I promise Sam?"})
    assert client.get("/api/memory").json()["image_readings_held"] == 5


def test_forget_now_clears_memory_unloads_the_model_and_the_app_stays_open(
    client: TestClient, runtime: Runtime
) -> None:
    client.post("/api/ask", json={"question": "What did I promise Sam?"})
    after = client.post("/api/forget").json()
    assert after["items_held"] == 0 and after["items_by_source"] == {}
    assert after["image_readings_held"] == 0 and after["model_loaded"] is False
    assert isinstance(runtime.gateway, FakeGateway) and runtime.gateway.unloads == 1
    assert runtime.session is not None and runtime.session.store.items() == []
    # Access choices are kept: the next question reads the allowed sources again.
    again = client.post("/api/ask", json={"question": "What did I promise Sam?"}).json()
    assert again["kind"] == "brief" and client.get("/api/memory").json()["items_held"] == 38


def test_revoking_a_source_shows_in_the_panel_at_once(client: TestClient) -> None:
    client.post("/api/sources/folder:notes/revoke")
    assert "Note files" not in client.get("/api/memory").json()["items_by_source"]


def test_the_process_list_names_this_backend_with_its_real_memory() -> None:
    processes = watched(server_pid=None)
    backend = next(p for p in processes if p.name == BACKEND)
    assert backend.pid == os.getpid() and backend.memory_mb > 5
    assert watched(server_pid=999_999_999)[0].name == BACKEND  # an unknown pid is left out
