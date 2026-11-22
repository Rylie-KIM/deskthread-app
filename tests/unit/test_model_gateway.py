"""Gateway tests (G3, FT-09, FT-45) against a fake model server on 127.0.0.1, and the
import allowlist (R3, U6): only the gateway may open a connection, and no database or index
library is used anywhere."""

import json
import re
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, ClassVar

import pytest

from app import config
from app.model import ModelGateway, complete_json, parse_json_object
from contracts.errors import DeskThreadError, ErrorCode

REPO = Path(__file__).resolve().parents[2]


class _Fake(BaseHTTPRequestHandler):
    digest: ClassVar[str] = config.MODEL_DIGEST
    loaded: ClassVar[bool] = False
    seen: ClassVar[list[dict[str, Any]]] = []

    def _send(self, body: dict[str, Any]) -> None:
        data = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        cls = type(self)
        if self.path == "/api/tags":
            self._send({"models": [{"name": config.MODEL_TAG, "digest": cls.digest}]})
        elif self.path == "/api/ps":
            self._send({"models": [{"name": config.MODEL_TAG}] if cls.loaded else []})
        else:
            self._send({"version": "fake"})

    def do_POST(self) -> None:
        cls = type(self)
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        cls.seen.append(body)
        if self.path == "/api/generate":
            cls.loaded = body.get("keep_alive") != 0
            self._send({"done": True})
        else:
            cls.loaded = True
            self._send({"message": {"content": 'Sure. {"points": []}'}})

    def log_message(self, *args: object) -> None:
        return None


@pytest.fixture
def fake() -> Iterator[str]:
    _Fake.digest, _Fake.loaded, _Fake.seen = config.MODEL_DIGEST, False, []
    server = HTTPServer(("127.0.0.1", 0), _Fake)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


@pytest.mark.parametrize(
    "url",
    ["http://localhost:11435", "http://192.168.1.10:11435", "https://127.0.0.1:11435",
     "http://example.com", "http://0.0.0.0:11435"],
)  # fmt: skip
def test_the_gateway_refuses_any_address_but_loopback(url: str) -> None:
    with pytest.raises(DeskThreadError) as err:
        ModelGateway(url)
    assert err.value.code is ErrorCode.MODEL_UNAVAILABLE


def test_a_call_sends_temperature_zero_a_seed_and_no_tools(fake: str) -> None:
    gateway = ModelGateway(fake)
    assert gateway.complete("hello", images=[b"png-bytes"]).endswith("}")
    sent = _Fake.seen[-1]
    assert sent["model"] == config.MODEL_TAG and sent["stream"] is False
    assert sent["options"] == {"temperature": 0, "seed": config.MODEL_SEED}
    assert "tools" not in sent and "format" not in sent
    assert sent["messages"][0]["images"] == ["cG5nLWJ5dGVz"]


def test_a_model_with_another_digest_is_refused(fake: str) -> None:
    _Fake.digest = "0" * 64
    with pytest.raises(DeskThreadError) as err:
        ModelGateway(fake).complete("hello")
    assert err.value.code is ErrorCode.MODEL_NOT_PINNED
    assert _Fake.seen == []  # nothing was sent to the unpinned model


def test_unload_is_verified(fake: str) -> None:
    gateway = ModelGateway(fake)
    gateway.complete("hello")
    assert gateway.loaded()
    assert gateway.unload() is True
    assert not gateway.loaded()


def test_a_server_that_is_not_there_is_an_error_with_a_code() -> None:
    gateway = ModelGateway("http://127.0.0.1:9")
    assert gateway.available() is False
    with pytest.raises(DeskThreadError) as err:
        gateway.complete("hello")
    assert err.value.code is ErrorCode.MODEL_UNAVAILABLE


def test_json_is_taken_from_the_reply_and_bad_replies_are_retried_once() -> None:
    assert parse_json_object('ok {"a": 1} thanks') == {"a": 1}

    class Flaky:
        def __init__(self) -> None:
            self.replies = ["no json here", '{"points": [1]}']

        def complete(self, prompt: str, images: list[bytes] | None = None) -> str:
            return self.replies.pop(0)

    assert complete_json(Flaky(), "q") == {"points": [1]}

    class Never:
        def complete(self, prompt: str, images: list[bytes] | None = None) -> str:
            return "[1, 2]"

    with pytest.raises(DeskThreadError) as err:
        complete_json(Never(), "q")
    assert err.value.code is ErrorCode.MODEL_BAD_OUTPUT


NETWORK = re.compile(
    r"^\s*(?:import|from)\s+(urllib\.request|urllib3|http\.client|socket|requests|httpx|aiohttp"
    r"|ftplib|smtplib|websockets?)\b",
    re.M,
)
STORAGE = re.compile(
    r"^\s*(?:import|from)\s+(sqlite3|dbm|shelve|pickle|chromadb|faiss|lancedb|whoosh|duckdb"
    r"|sqlalchemy|redis|tempfile|logging\.handlers)\b",
    re.M,
)


def test_only_the_gateway_may_open_a_connection() -> None:
    """The full list of network modules in the app, each with its one reason."""
    allowed = {
        "app/model.py": {"urllib.request"},  # calls the model server on 127.0.0.1
        "app/__main__.py": {"socket"},  # asks the OS for a free loopback port; connects nowhere
    }
    users = {
        str(p.relative_to(REPO)): set(NETWORK.findall(p.read_text()))
        for folder in ("app", "contracts")
        for p in (REPO / folder).rglob("*.py")
        if NETWORK.search(p.read_text())
    }
    assert users == allowed
    launcher = (REPO / "app" / "__main__.py").read_text()
    assert ".connect(" not in launcher and "host=config.LOOPBACK" in launcher


def test_u6_no_database_index_or_temp_file_library_is_imported() -> None:
    for folder in ("app", "contracts"):
        for path in (REPO / folder).rglob("*.py"):
            assert not STORAGE.search(path.read_text()), path
    declared = (REPO / "pyproject.toml").read_text().split("[dependency-groups]")[0]
    for name in ("sqlite", "chroma", "faiss", "lancedb", "duckdb", "redis", "sqlalchemy"):
        assert name not in declared.lower()


def test_a_server_left_over_on_our_port_is_adopted_and_stopped_at_the_end(
    fake: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.model import ModelServer

    killed: list[tuple[int, int]] = []
    monkeypatch.setattr(ModelServer, "_listener", staticmethod(lambda: 4242))
    monkeypatch.setattr("app.model.os.kill", lambda pid, sig: killed.append((pid, sig)))
    server = ModelServer()
    assert server.start(ModelGateway(fake)) is True  # something already answers: adopt it
    assert server.pid == 4242
    server.stop()
    assert [pid for pid, _ in killed] == [4242] and server.pid is None
    server.stop()
    assert len(killed) == 1  # stopping twice is harmless


# ------------------------------------------------------------------ choosing a model (T-47)


def test_only_approved_models_and_no_chinese_developed_one_is_offered() -> None:
    makers = {m.maker for m in config.MODELS}
    # The families discussed in the plan (5k): labs in the US and Europe only.
    assert makers <= {
        "Google", "Microsoft", "IBM", "Meta", "Mistral AI", "OpenAI", "NVIDIA", "Hugging Face",
        "Allen Institute for AI",
    }  # fmt: skip
    assert [m.tag for m in config.MODELS if m.digest] == [
        "gemma4:e4b", "gemma4:e2b", "phi4-mini:latest"
    ]  # fmt: skip  # only these were run; the others are offered untested and unpinned
    assert all(not m.reads_pictures for m in config.MODELS if not m.digest)
    assert (
        config.MODELS[0].tag == config.MODEL_TAG and config.MODELS[0].digest == config.MODEL_DIGEST
    )
    assert len({m.tag for m in config.MODELS}) == len(config.MODELS)
    assert config.model_choice("qwen3:8b") is None and config.model_choice("deepseek-r1") is None


def test_selecting_a_model_needs_it_approved_and_on_this_mac(fake: str) -> None:
    gateway = ModelGateway(fake)
    gateway.complete("hello")
    assert gateway.tag == config.MODEL_TAG and gateway.reads_pictures is True
    for tag, code in (
        ("qwen3:8b", ErrorCode.BAD_REQUEST),
        ("phi4-mini:latest", ErrorCode.MODEL_UNAVAILABLE),
    ):
        with pytest.raises(DeskThreadError) as err:
            gateway.select(tag)
        assert err.value.code is code
    assert gateway.tag == config.MODEL_TAG  # a refused choice changes nothing
