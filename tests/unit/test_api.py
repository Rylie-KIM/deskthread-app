"""U5 and the API click path (FT-23, FT-42, FT-14, FT-33) with a scripted fake model."""

from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.api import create_app
from app.runtime import Runtime
from contracts.api import ROUTES, TOKEN_HEADER
from contracts.errors import DeskThreadError, ErrorCode
from tests.fakes import SAM_BRIEF, STORY_NOW, FakeModel, wait_until_prepared

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
        if source["blocked"]:
            continue  # this AI model cannot use it (pictures)
        request = client.get(f"/api/sources/{source['source_id']}/request").json()
        skip = ("personal", "WhatsApp", "KakaoTalk")
        scopes = [
            s["scope_id"] for s in request["scopes"] if not any(w in s["scope_id"] for w in skip)
        ]
        assert client.post(
            f"/api/sources/{source['source_id']}/grant", json={"scope_ids": scopes}
        ).is_success
    wait_until_prepared(client)  # pictures are read in the background after the switch


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


def test_several_folders_at_once_and_removing_one_drops_it_from_memory(
    client: TestClient, runtime: Runtime, demo_laptop: Path, tmp_path: Path
) -> None:
    _work_profile(client, demo_laptop)
    held = len(runtime.session.store.items())
    assert held > 40

    extra = tmp_path / "Meeting notes"
    extra.mkdir()
    (extra / "offsite.txt").write_text("Offsite 14 Jan\nbook the venue")  # a file at the top
    (extra / "deep").mkdir()
    (extra / "deep" / "more.md").write_text("more notes")
    added = client.post("/api/folder", json={"path": str(extra)}).json()
    states = {s["source_id"]: s for s in added}
    assert states["folder:notes"]["status"] == "on"  # what was On stays On
    assert len(runtime.session.store.items()) == held  # and stays in memory
    names = [f["name"] for f in client.get("/api/folders").json()]
    assert names == ["demo-laptop", "Meeting notes"]

    request = client.get("/api/sources/folder:documents/request").json()
    labels = {s["label"]: s["item_count"] for s in request["scopes"]}
    assert labels["Meeting notes"] == 2  # the new folder is one piece, top-level files included
    chosen = [s["scope_id"] for s in request["scopes"] if s["label"] == "Meeting notes"]
    client.post("/api/sources/folder:documents/grant", json={"scope_ids": chosen})
    locations = {i.location for i in runtime.session.store.items()}
    assert {"Meeting notes/offsite.txt", "Meeting notes/deep/more.md"} <= locations

    client.post("/api/folder/remove", json={"path": str(demo_laptop)})
    left = {i.location for i in runtime.session.store.items()}
    assert left == {"offsite.txt", "deep/more.md"}  # only the remaining folder is held
    assert [f["name"] for f in client.get("/api/folders").json()] == ["Meeting notes"]
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

        def unload(self, wait_s: float = 20) -> bool:
            return True

        def verify_pin(self) -> str:
            return "ok"

    runtime.gateway = Installed()
    client = TestClient(create_app(runtime), base_url=BASE, headers={TOKEN_HEADER: runtime.token})
    listed = {m["tag"]: m for m in client.get("/api/models").json()}
    assert listed["gemma4:e4b"]["selected"] and listed["gemma4:e4b"]["tested"]
    assert listed["gemma4:e2b"]["installed"] is False and listed["gemma4:e2b"]["tested"] is True
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
    assert client.get("/api/progress").json() == {"step": "", "number": 0, "of": 0, "detail": ""}
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


def test_the_policy_follows_a_page_rebuilt_while_the_app_runs(tmp_path: Path) -> None:
    page = tmp_path / "index.html"
    page.write_text("<script>first()</script>")
    runtime = Runtime(FakeModel(lambda q: []), PORT)
    client = TestClient(
        create_app(runtime, tmp_path), base_url=BASE, headers={TOKEN_HEADER: runtime.token}
    )
    before = client.get("/api/session").headers["content-security-policy"]
    page.write_text("<script>second_build()</script>")
    after = client.get("/api/session").headers["content-security-policy"]
    assert "sha256-" in before and "sha256-" in after and before != after


def test_an_app_icon_is_served_as_a_png_and_unknown_sources_have_none(
    client: TestClient, runtime: Runtime
) -> None:
    pytest.importorskip("AppKit")
    shown = client.get("/api/sources/mac:calendar/icon")
    assert shown.status_code == 200 and shown.headers["content-type"] == "image/png"
    assert shown.content[:8] == b"\x89PNG\r\n\x1a\n" and len(shown.content) > 2000
    assert client.get("/api/sources/folder:notes/icon").status_code == 404
    bare = TestClient(create_app(runtime), base_url=BASE)
    assert bare.get("/api/sources/mac:calendar/icon").status_code == 401
    assert bare.get(f"/api/sources/mac:calendar/icon?t={runtime.token}").status_code == 200


def test_a_question_reads_folders_again_but_not_the_apps(
    client: TestClient, runtime: Runtime, demo_laptop: Path
) -> None:
    from app.sources.mac import MacAppAdapter
    from contracts.items import SourceKind
    from tests.unit.test_mac_apps import FakeApps

    apps = FakeApps()
    runtime.session.broker.register(MacAppAdapter("notes", SourceKind.NOTES, "Notes", "/", apps))
    _work_profile(client, demo_laptop)
    client.post("/api/sources/mac:notes/grant", json={"scope_ids": ["DeskThread Demo"], "days": 30})
    reads = [name for name, _ in apps.calls if name == "notes.read"]
    grant = runtime.session.broker.read_grant("mac:notes")
    assert reads and getattr(grant, "days", None) == 30
    client.post("/api/ask", json={"question": "What did I promise Sam?"})
    client.post("/api/ask", json={"question": "What did I promise Sam?"})
    assert [name for name, _ in apps.calls if name == "notes.read"] == reads  # not asked again


def test_a_question_can_be_stopped(client: TestClient, runtime: Runtime, demo_laptop: Path) -> None:
    _work_profile(client, demo_laptop)
    model = runtime.session.assistant._model
    original = model.complete

    def pressing_stop(prompt: str, images: list[bytes] | None = None) -> str:
        client.post("/api/cancel")  # the user presses Stop while the AI is working
        return original(prompt, images)

    model.complete = pressing_stop  # type: ignore[method-assign]
    stopped = client.post("/api/ask", json={"question": "What did I promise Sam?"}).json()
    assert stopped["kind"] == "stopped" and stopped["points"] == []
    model.complete = original  # type: ignore[method-assign]
    again = client.post("/api/ask", json={"question": "What did I promise Sam?"}).json()
    assert again["kind"] == "brief"  # the next question runs normally
    assert runtime.session.assistant.readings_held == 5  # the pictures were read when switched on


def test_the_pictures_are_prepared_in_the_background_and_say_how_far_they_are(
    client: TestClient, runtime: Runtime, demo_laptop: Path
) -> None:
    model = runtime.session.assistant._model
    seen: list[dict[str, object]] = []
    original = model.complete

    def watching(prompt: str, images: list[bytes] | None = None) -> str:
        if images:
            seen.append(client.get("/api/preparing").json())  # asked while a picture is read
        return original(prompt, images)

    model.complete = watching  # type: ignore[method-assign]
    assert client.get("/api/preparing").json() == {
        "active": False,
        "done": 0,
        "total": 0,
        "what": "",
    }
    for source in client.post("/api/folder", json={"path": str(demo_laptop)}).json():
        if source["source_id"] == "folder:images":
            client.post("/api/sources/folder:images/grant", json={})  # returns at once
    wait_until_prepared(client)
    assert [s["done"] for s in seen] == [1, 2, 3, 4, 5] and all(s["total"] == 5 for s in seen)
    assert all(s["active"] is True for s in seen)
    ready = client.get("/api/preparing").json()
    assert ready["active"] is False  # the chat opens
    assert ready["what"] == "Pictures ready" and ready["done"] == ready["total"] == 5
    assert runtime.session.assistant.readings_held == 5


def test_folders_say_what_they_hold_and_what_cannot_be_read(
    client: TestClient, tmp_path: Path
) -> None:
    for name in ("a.pdf", "b.txt", "shot.png", "clip.mov", "talk.mp4", "data.xyz"):
        (tmp_path / name).write_bytes(b"x")
    client.post("/api/folder", json={"path": str(tmp_path)})
    (info,) = client.get("/api/folders").json()
    assert (info["files"], info["pictures"], info["videos"], info["other"]) == (2, 1, 2, 1)
    memory = client.get("/api/memory").json()
    assert memory["mac_memory_mb"] > 1000 and 0 < memory["mac_free_mb"] < memory["mac_memory_mb"]


def test_the_original_of_an_item_is_shown_by_its_own_checked_path_only(
    client: TestClient, runtime: Runtime, demo_laptop: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ran: list[list[str]] = []

    class Done:
        returncode = 0

    def fake_run(command: list[str], **_: object) -> Done:
        ran.append(command)
        return Done()

    monkeypatch.setattr("app.icons.subprocess.run", fake_run)
    _work_profile(client, demo_laptop)
    held = runtime.session.store.items()
    note = next(i for i in held if i.meta.get("path"))
    shown = client.post(f"/api/items/{note.item_id}/reveal")
    assert shown.status_code == 200 and shown.json()["origin"] == "file"
    assert ran == [["/usr/bin/open", "-R", note.meta["path"]]]  # selected in Finder, not opened
    assert Path(note.meta["path"]).is_relative_to(demo_laptop.resolve())
    client.post("/api/sources/revoke-all")
    assert client.post(f"/api/items/{note.item_id}/reveal").status_code != 200  # Off: not shown
    assert len(ran) == 1


def test_spellings_of_a_name_are_kept_for_the_session_and_survive_clear_memory(
    client: TestClient, runtime: Runtime, demo_laptop: Path
) -> None:
    _work_profile(client, demo_laptop)
    assert client.get("/api/people").json() == []
    saved = client.post("/api/people", json=[{"name": " Sam ", "also": ["Sammy", " ", "Samuel"]}])
    assert saved.json() == [{"name": "Sam", "also": ["Sammy", "Samuel"]}]
    client.post("/api/forget")
    assert client.get("/api/people").json() == saved.json()
    assert client.post("/api/people", json=[{"name": "", "also": []}]).status_code == 422


def test_choosing_and_removing_a_folder_is_logged_once_each(
    client: TestClient, tmp_path: Path
) -> None:
    (tmp_path / "a.txt").write_text("x")
    client.post("/api/folder", json={"path": str(tmp_path)})
    client.post("/api/folder", json={"path": str(tmp_path)})  # the same folder again: no new line
    client.post("/api/folder/remove", json={"path": str(tmp_path)})
    client.post("/api/folder/remove", json={"path": str(tmp_path)})
    lines = [
        (a["action"], a["source_id"])
        for a in client.get("/api/proof").json()["audit"]
        if a["action"].startswith("folder_")
    ]
    assert lines == [
        ("folder_added", f"dir:{tmp_path.name}"),
        ("folder_removed", f"dir:{tmp_path.name}"),
    ]


def test_pictures_cannot_be_switched_on_with_a_model_that_does_not_read_them(
    client: TestClient, runtime: Runtime, tmp_path: Path
) -> None:
    (tmp_path / "shot.png").write_bytes(b"x")
    (tmp_path / "note.txt").write_text("a note")
    sources = {
        s["source_id"]: s for s in client.post("/api/folder", json={"path": str(tmp_path)}).json()
    }
    assert set(sources) == {"folder:documents", "folder:images"}
    assert all(s["blocked"] == "" for s in sources.values())
    model = runtime.session.assistant._model
    request = client.get("/api/sources/folder:images/request").json()
    scopes = [s["scope_id"] for s in request["scopes"]]
    assert client.post("/api/sources/folder:images/grant", json={"scope_ids": scopes}).is_success
    model.reads_pictures = False  # type: ignore[attr-defined]  # a model without pictures
    now_blocked = {s["source_id"]: s for s in client.get("/api/sources").json()}
    assert (
        now_blocked["folder:images"]["blocked"] and now_blocked["folder:documents"]["blocked"] == ""
    )
    assert client.post("/api/sources/folder:images/revoke").is_success
    refused = client.post("/api/sources/folder:images/grant", json={"scope_ids": scopes})
    assert refused.status_code == 400
    assert client.post("/api/sources/folder:documents/grant", json={"scope_ids": []}).is_success


def test_a_folder_has_only_the_rows_for_what_it_holds(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "shot.png").write_bytes(b"x")
    only_pictures = {
        s["source_id"] for s in client.post("/api/folder", json={"path": str(tmp_path)}).json()
    }
    assert only_pictures == {"folder:images"}  # no empty "Files" row
    other = tmp_path / "docs"
    other.mkdir()
    (other / "a.txt").write_text("text")
    both = {s["source_id"] for s in client.post("/api/folder", json={"path": str(other)}).json()}
    assert both == {"folder:images", "folder:documents"}


def test_stop_cuts_the_request_that_is_with_the_ai_and_ends_the_question_as_stopped(
    client: TestClient, runtime: Runtime, demo_laptop: Path
) -> None:
    _work_profile(client, demo_laptop)
    model = runtime.session.assistant._model
    aborted: list[bool] = []
    model.abort = lambda: aborted.append(True)  # type: ignore[attr-defined]
    original = model.complete

    def stopping(prompt: str, images: list[bytes] | None = None) -> str:
        client.post("/api/cancel")  # the user presses Stop while the AI is working
        raise DeskThreadError(ErrorCode.MODEL_UNAVAILABLE)  # the request was cut off

    model.complete = stopping  # type: ignore[method-assign]
    answer = client.post("/api/ask", json={"question": "What did I promise Sam?"}).json()
    assert aborted and answer["kind"] == "stopped" and answer["points"] == []
    model.complete = original  # type: ignore[method-assign]
    assert (
        client.post("/api/ask", json={"question": "What did I promise Sam?"}).json()["kind"]
        == "brief"
    )
