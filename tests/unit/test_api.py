"""U5 and the API click path (FT-23, FT-42, FT-14, FT-33) with a scripted fake model."""

from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.api import create_app
from app.runtime import Runtime
from contracts.api import ROUTES, TOKEN_HEADER
from tests.fakes import SAM_BRIEF, STORY_NOW, FakeModel

PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"


@pytest.fixture(autouse=True)
def clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DESKTHREAD_NOW", STORY_NOW)


@pytest.fixture
def runtime() -> Runtime:
    return Runtime(FakeModel(lambda q: SAM_BRIEF), PORT)


@pytest.fixture
def client(runtime: Runtime) -> TestClient:
    return TestClient(create_app(runtime), base_url=BASE, headers={TOKEN_HEADER: runtime.token})


def _work_profile(client: TestClient, demo_laptop: Path) -> None:
    for source in client.post("/api/folder", json={"path": str(demo_laptop)}).json():
        request = client.get(f"/api/sources/{source['source_id']}/request").json()
        skip = ("personal", "WhatsApp", "KakaoTalk")
        scopes = [
            s["scope_id"] for s in request["scopes"] if not any(w in s["scope_id"] for w in skip)
        ]
        assert client.post(
            f"/api/sources/{source['source_id']}/grant", json={"scope_ids": scopes}
        ).is_success


# ------------------------------------------------------------------ U5: local API protection


def test_u5_a_request_without_the_token_is_rejected(runtime: Runtime) -> None:
    bare = TestClient(create_app(runtime), base_url=BASE)
    assert bare.get("/api/session").status_code == 401
    assert bare.get("/api/session").json()["code"] == "E-501"
    wrong = bare.get("/api/session", headers={TOKEN_HEADER: "x" * 43})
    assert wrong.status_code == 401
    assert bare.get("/api/session", headers={TOKEN_HEADER: runtime.token}).status_code == 200


def test_u5_a_wrong_origin_or_host_is_rejected(client: TestClient, runtime: Runtime) -> None:
    other_site = client.get("/api/session", headers={"Origin": "https://evil.example"})
    assert (other_site.status_code, other_site.json()["code"]) == (403, "E-502")
    for host in ("localhost:8765", "127.0.0.1:9999", "evil.example", "192.168.0.5:8765"):
        rebound = client.get("/api/session", headers={"Host": host})
        assert (rebound.status_code, rebound.json()["code"]) == (400, "E-503"), host
    assert client.get("/api/session", headers={"Origin": BASE}).status_code == 200


def test_the_demo_folder_is_offered_only_if_our_generator_built_it(
    demo_laptop: Path, tmp_path: Path
) -> None:
    def offered(folder: Path | None) -> str:
        runtime = Runtime(FakeModel(lambda q: []), PORT, demo_folder=folder)
        client = TestClient(
            create_app(runtime), base_url=BASE, headers={TOKEN_HEADER: runtime.token}
        )
        return str(client.get("/api/session").json()["demo_folder"])

    assert offered(demo_laptop) == str(demo_laptop)
    assert offered(tmp_path) == "" and offered(None) == ""  # some other folder is never offered


def test_a_new_launch_gets_a_new_token() -> None:
    first, second = Runtime(FakeModel(lambda q: []), PORT), Runtime(FakeModel(lambda q: []), PORT)
    assert first.token != second.token and len(first.token) >= 40


def test_every_reply_says_do_not_store_and_allows_no_outside_resource(
    client: TestClient,
) -> None:
    for response in (client.get("/api/session"), client.get("/api/nothing-here")):
        assert response.headers["cache-control"] == "no-store"
        csp = response.headers["content-security-policy"]
        assert "default-src 'none'" in csp and "connect-src 'self'" in csp
        assert "http:" not in csp and "https:" not in csp and "*" not in csp
        assert response.headers["x-content-type-options"] == "nosniff"


def test_the_api_serves_exactly_the_routes_of_the_contract_so_far(runtime: Runtime) -> None:
    served = {
        f"{method} {route.path}"
        for route in create_app(runtime).routes
        if isinstance(route, APIRoute)
        for method in (route.methods or set()) - {"HEAD", "OPTIONS"}
    }
    assert served <= set(ROUTES)
    assert {"POST /api/ask", "POST /api/sources/{source_id}/revoke"} <= served


# ------------------------------------------------------------------ the click path


def test_before_a_folder_is_chosen_there_is_nothing(client: TestClient) -> None:
    assert client.get("/api/sources").json() == []
    assert client.get("/api/meetings").json() == []
    asked = client.post("/api/ask", json={"question": "anything"}).json()
    assert asked["kind"] == "no_sources" and asked["coverage"]["accessible"] == 0


def test_choose_folder_work_profile_prepare_and_revoke(
    client: TestClient, demo_laptop: Path
) -> None:
    states = client.post("/api/folder", json={"path": str(demo_laptop)}).json()
    assert {s["status"] for s in states} == {"off"}  # everything starts Off, chat apps too

    _work_profile(client, demo_laptop)
    meeting = client.get("/api/meetings").json()[1]
    assert (meeting["title"], meeting["person"]) == ("1:1 Sam", "Sam")
    answer = client.post("/api/prepare", json={"meeting_id": meeting["meeting_id"]}).json()
    assert answer["kind"] == "brief" and len(answer["points"]) == 4
    assert answer["coverage"]["cited"] == 4

    state = client.post("/api/sources/folder:notes/revoke").json()
    assert (state["status"], state["items_in_memory"]) == ("off", 0)
    after = client.post("/api/ask", json={"question": "What did I promise Sam?"}).json()
    assert all(c["source_id"] != "folder:notes" for p in after["points"] for c in p["citations"])
    stopped = client.post("/api/sources/revoke-all").json()
    assert all(s["status"] != "on" for s in stopped)
    assert client.post("/api/ask", json={"question": "x"}).json()["kind"] == "no_sources"


def test_the_viewer_shows_a_cited_note_as_text_and_only_while_its_source_is_on(
    client: TestClient, demo_laptop: Path
) -> None:
    _work_profile(client, demo_laptop)
    answer = client.post("/api/ask", json={"question": "What did I promise Sam?"}).json()
    cite = answer["points"][1]["citations"][0]
    view = client.get(f"/api/items/{cite['item_id']}").json()
    assert view["title"] == "follow-ups" and view["source_label"] == "Note files"
    assert view["units"][cite["unit"] - 1]["text"] == cite["quote"]
    client.post("/api/sources/folder:notes/revoke")
    gone = client.get(f"/api/items/{cite['item_id']}")
    assert (gone.status_code, gone.json()["message"]) == (409, "not visible")


def test_an_image_is_served_to_the_page_only_with_the_token(
    client: TestClient, runtime: Runtime, demo_laptop: Path
) -> None:
    _work_profile(client, demo_laptop)
    client.post("/api/ask", json={"question": "What did I promise Sam?"})
    assert runtime.session is not None
    image = next(
        i for i in runtime.session.store.items() if i.location.endswith("office-plant.png")
    )
    ok = client.get(f"/api/items/{image.item_id}/image")
    assert ok.status_code == 200 and ok.headers["content-type"] == "image/png"
    bare = TestClient(create_app(runtime), base_url=BASE)
    assert bare.get(f"/api/items/{image.item_id}/image").status_code == 401
    assert bare.get(f"/api/items/{image.item_id}/image?t={runtime.token}").status_code == 200
    note = next(i for i in runtime.session.store.items() if i.location.endswith("follow-ups.md"))
    assert client.get(f"/api/items/{note.item_id}/image").status_code == 409


def test_choosing_a_new_folder_drops_the_old_one_from_memory(
    client: TestClient, runtime: Runtime, demo_laptop: Path, tmp_path: Path
) -> None:
    _work_profile(client, demo_laptop)
    assert len(runtime.session.store.items()) > 40
    (tmp_path / "Work").mkdir()
    assert client.post("/api/folder", json={"path": str(tmp_path)}).is_success
    assert runtime.session.store.items() == []  # the old folder's items left memory
    assert all(s.status.value == "off" for s in runtime.session.broker.states())
    assert {s.source_id for s in runtime.session.broker.states()} == {
        "folder:documents",
        "folder:images",
    }
    assert client.post("/api/folder", json={"path": str(tmp_path / "missing")}).status_code == 400


def test_inline_scripts_of_our_own_page_are_allowed_by_hash_and_nothing_else(
    tmp_path: Path,
) -> None:
    from app.api import content_security_policy, script_hashes

    (tmp_path / "index.html").write_text(
        '<script src="/a.js"></script><script>boot()</script>'
        '<script id="d" type="application/json">{"a":1}</script>'
    )
    hashes = script_hashes(tmp_path)
    assert len(hashes) == 1 and hashes[0].startswith("'sha256-")  # only the executable one
    csp = content_security_policy(tmp_path)
    assert f"script-src 'self' {hashes[0]};" in csp
    assert "'unsafe-inline'" not in csp.split("style-src")[0]  # never for scripts
    assert content_security_policy(None).count("sha256") == 0


def test_the_model_list_shows_what_is_approved_installed_and_in_use(runtime: Runtime) -> None:
    from app.model import ModelGateway

    class Installed(ModelGateway):
        def installed(self) -> dict[str, str]:
            return {"gemma4:e4b": "d" * 64, "phi4-mini:latest": "e" * 64}

        def unload(self) -> bool:
            return True

        def verify_pin(self) -> str:
            return "ok"

    runtime.gateway = Installed()
    client = TestClient(create_app(runtime), base_url=BASE, headers={TOKEN_HEADER: runtime.token})
    listed = {m["tag"]: m for m in client.get("/api/models").json()}
    assert listed["gemma4:e4b"]["selected"] and listed["gemma4:e4b"]["tested"]
    assert listed["gemma4:e2b"]["installed"] is False and listed["gemma4:e2b"]["tested"] is False
    assert listed["phi4-mini:latest"]["reads_pictures"] is False

    picked = client.post("/api/models/select", json={"tag": "phi4-mini:latest"}).json()
    assert {m["tag"] for m in picked if m["selected"]} == {"phi4-mini:latest"}
    assert client.get("/api/session").json()["model_tag"] == "phi4-mini:latest"
    assert client.post("/api/models/select", json={"tag": "gemma4:e2b"}).status_code == 503
    assert client.post("/api/models/download", json={"tag": "qwen3:8b"}).status_code == 400


def test_a_model_that_cannot_read_pictures_leaves_them_unread(demo_laptop: Path) -> None:
    model = FakeModel(lambda q: SAM_BRIEF)
    model.reads_pictures = False  # type: ignore[attr-defined]
    runtime = Runtime(model, PORT)
    client = TestClient(create_app(runtime), base_url=BASE, headers={TOKEN_HEADER: runtime.token})
    _work_profile(client, demo_laptop)
    client.post("/api/ask", json={"question": "What did I promise Sam?"})
    assert all("Transcribe" not in p for p in model.prompts)  # no picture was sent to the model
    assert runtime.session.assistant.readings_held == 0


def test_progress_is_empty_when_nothing_runs_and_names_the_step_while_a_question_runs(
    client: TestClient, runtime: Runtime, demo_laptop: Path
) -> None:
    _work_profile(client, demo_laptop)
    assert client.get("/api/progress").json() == {"step": "", "number": 0, "of": 0}
    seen: list[dict[str, object]] = []
    model = runtime.session.assistant._model
    original = model.complete

    def watching(prompt: str, images: list[bytes] | None = None) -> str:
        seen.append(client.get("/api/progress").json())  # asked while the question is running
        return original(prompt, images)

    model.complete = watching  # type: ignore[method-assign]
    client.post("/api/ask", json={"question": "What did I promise Sam?"})
    steps = {str(s["step"]) for s in seen}
    assert "Asking the AI on this Mac" in steps and all(s["of"] == 5 for s in seen)
    assert client.get("/api/progress").json()["step"] == ""  # cleared when the answer is back
