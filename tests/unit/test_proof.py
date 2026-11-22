"""The Proof panel (FT-17, FT-18, FT-19, FT-22): connections, fingerprint, writes, limits."""

import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.proof import evidence
from app.runtime import Runtime
from contracts.api import TOKEN_HEADER
from tests.conftest import CANARY
from tests.fakes import SAM_BRIEF, STORY_NOW, FakeModel

PORT = 8765
LSOF = """\
COMMAND   PID USER   FD   TYPE DEVICE SIZE/OFF NODE NAME
python   4101 me     8u  IPv4 0x1      0t0  TCP 127.0.0.1:8765 (LISTEN)
python   4101 me     9u  IPv4 0x2      0t0  TCP 127.0.0.1:52001->127.0.0.1:11435 (ESTABLISHED)
ollama   4102 me     5u  IPv4 0x3      0t0  TCP 127.0.0.1:11435 (LISTEN)
ollama   4102 me     6u  IPv4 0x4      0t0  TCP 192.168.1.20:52002->203.0.113.9:443 (ESTABLISHED)
ollama   4102 me     7u  IPv6 0x5      0t0  TCP *:11434 (LISTEN)
"""


def _files_in(folder: Path) -> int:
    """Every file under the folder, the demo marker included (the fingerprint covers all)."""
    return sum(1 for p in folder.rglob("*") if p.is_file())


@pytest.fixture(autouse=True)
def clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DESKTHREAD_NOW", STORY_NOW)


@pytest.fixture
def laptop(demo_laptop: Path, tmp_path: Path) -> Path:
    root = tmp_path / "demo-laptop"
    shutil.copytree(demo_laptop, root)
    return root


@pytest.fixture
def client(laptop: Path) -> TestClient:
    runtime = Runtime(FakeModel(lambda q: SAM_BRIEF), PORT)
    client = TestClient(
        create_app(runtime),
        base_url=f"http://127.0.0.1:{PORT}",
        headers={TOKEN_HEADER: runtime.token},
    )
    client.post("/api/folder", json={"path": str(laptop)})
    for source in ("folder:notes", "folder:mail"):
        client.post(f"/api/sources/{source}/grant", json={})
    return client


def test_connections_are_local_only_and_an_outside_one_is_flagged() -> None:
    found = evidence.parse_lsof(LSOF, {4101: "DeskThread backend", 4102: "Model server"})
    assert [c.local_only for c in found] == [True, True, True, False, False]
    assert found[0].remote == "127.0.0.1:8765 (listening)"
    assert found[1].remote == "127.0.0.1:11435" and found[1].process == "DeskThread backend"
    assert found[3].remote == "203.0.113.9:443"  # an outside address would show up, by name
    assert found[4].remote.startswith("*:")  # listening on every interface is not local


def test_the_fingerprint_matches_after_questions_and_changes_when_a_file_changes(
    client: TestClient, laptop: Path
) -> None:
    client.post("/api/ask", json={"question": "What did I promise Sam?"})
    folder = client.get("/api/proof").json()["folders"][0]
    assert folder["unchanged"] is True and folder["before"] == folder["now"]
    assert folder["label"] == "demo-laptop" and folder["files"] == _files_in(laptop)
    (laptop / "Desktop" / "todo-scribble.txt").write_text("changed outside the app")
    assert client.get("/api/proof").json()["folders"][0]["unchanged"] is False


def test_the_fingerprint_opens_no_file(laptop: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a file was opened")

    monkeypatch.setattr("builtins.open", refuse)
    monkeypatch.setattr(Path, "open", refuse)
    assert evidence.fingerprint(laptop)[1] == _files_in(
        laptop
    )  # private and off-limits files are covered too


def test_the_write_audit_counts_writes_and_ignores_reads(tmp_path: Path) -> None:
    evidence.install_write_audit()
    start = evidence.files_written()
    (tmp_path / "a.txt").write_text("x")
    with (tmp_path / "a.txt").open("rb") as handle:
        handle.read()
    with open(os.devnull, "w") as sink:  # noqa: PTH123
        sink.write("x")
    assert evidence.files_written() == start + 1


def test_answering_questions_writes_no_file(client: TestClient) -> None:
    evidence.install_write_audit()
    start = evidence.files_written()
    client.post("/api/ask", json={"question": "What did I promise Sam?"})
    client.post("/api/ask", json={"question": "What salary did I promise Sam?"})
    client.post("/api/forget")
    proof = client.get("/api/proof").json()
    assert evidence.files_written() == start  # L-4: the backend opened nothing for writing
    assert proof["files_written_by_app"] == start


def test_the_proof_holds_counts_and_ids_only_and_states_its_limits(
    laptop: Path, generator: object
) -> None:
    note = laptop / "App-exports" / "Notes" / "qbr-prep.md"
    note.write_text(note.read_text() + f"- ref {CANARY}\n")
    runtime = Runtime(FakeModel(lambda q: SAM_BRIEF), PORT)
    client = TestClient(
        create_app(runtime),
        base_url=f"http://127.0.0.1:{PORT}",
        headers={TOKEN_HEADER: runtime.token},
    )
    client.post("/api/folder", json={"path": str(laptop)})
    client.post("/api/sources/folder:notes/grant", json={})
    client.post("/api/ask", json={"question": "What did I promise Sam?"})
    text = client.get("/api/proof").text
    assert CANARY not in text and "conference" not in text and "qbr-prep" not in text
    proof = client.get("/api/proof").json()
    assert {line["action"] for line in proof["audit"]} >= {"grant", "read"}
    assert "cannot prove that memory was erased" in proof["limits"]
    assert set(proof["telemetry_off"]) >= {"OLLAMA_NO_CLOUD", "DO_NOT_TRACK"}


def test_a_changed_folder_names_the_files_with_time_and_owner_without_opening_them(
    tmp_path: Path,
) -> None:
    from app.proof.evidence import differences, listing

    (tmp_path / "keep.txt").write_text("same")
    (tmp_path / "edit.txt").write_text("old")
    (tmp_path / "gone.txt").write_text("bye")
    before = listing(tmp_path)
    assert differences(before, listing(tmp_path)) == []
    (tmp_path / "edit.txt").write_text("new and longer")
    (tmp_path / "new.txt").write_text("hello")
    (tmp_path / "gone.txt").unlink()
    found = {c.name: c for c in differences(before, listing(tmp_path))}
    assert {n: c.what for n, c in found.items()} == {
        "edit.txt": "changed", "new.txt": "added", "gone.txt": "removed"
    }  # fmt: skip
    assert found["edit.txt"].when is not None and found["edit.txt"].owner
    assert found["gone.txt"].when is None


def test_the_connection_check_hands_back_the_command_the_print_out_and_its_reading() -> None:
    import os

    from app.proof.evidence import check

    result = check({os.getpid(): "DeskThread"})
    assert result.command == f"lsof -nP -iTCP -a -p {os.getpid()}"
    assert result.all_local == all(c.local_only for c in result.connections)
    assert len(result.connections) <= max(0, len(result.output.splitlines()) - 1)
    assert check({}).command == "" and check({}).connections == ()
