"""Gate G3, the local model gateway (FT-09): the only code that talks to the model.

It is also the only module in app/ allowed to open a network connection, and it refuses any
address that is not 127.0.0.1 (a test checks both). The model has no tools: it gets text and
images and returns text, which is only ever displayed or parsed, never executed (FT-44).
"""

import base64
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from typing import Any, Protocol
from urllib.parse import urlparse

from app import config
from contracts.errors import DeskThreadError, ErrorCode


class Model(Protocol):
    """What the rest of the app needs from a model. Tests use a fake with this shape."""

    def complete(self, prompt: str, images: list[bytes] | None = None) -> str: ...


def parse_json_object(text: str) -> dict[str, Any]:
    """The first JSON object in a reply. The runtime cannot force JSON for this model
    (HTTP 501 on the format option, T-04), so the shape is checked here in code."""
    try:
        data = json.loads(text[text.index("{") : text.rindex("}") + 1])
    except ValueError as exc:
        raise DeskThreadError(ErrorCode.MODEL_BAD_OUTPUT) from exc
    if not isinstance(data, dict):
        raise DeskThreadError(ErrorCode.MODEL_BAD_OUTPUT)
    return data


def complete_json(model: Model, prompt: str, tries: int = 2) -> dict[str, Any]:
    """Ask for JSON and validate it; ask once more if the reply is not JSON."""
    for attempt in range(tries):
        try:
            return parse_json_object(model.complete(prompt))
        except DeskThreadError:
            if attempt == tries - 1:
                raise
    raise DeskThreadError(ErrorCode.MODEL_BAD_OUTPUT)


class ModelGateway:
    def __init__(self, base_url: str = f"http://{config.LOOPBACK}:{config.MODEL_PORT}") -> None:
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname != config.LOOPBACK:
            # Not "localhost" either: a name can be pointed somewhere else.
            raise DeskThreadError(ErrorCode.MODEL_UNAVAILABLE, "the model must be on 127.0.0.1")
        self._base = base_url.rstrip("/")
        self._pinned = False
        self.calls = 0

    def _call(self, path: str, body: dict[str, Any] | None = None, timeout: float = 300) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self._base + path, data=data)  # noqa: S310
        # No proxy, ever: a proxy would carry the prompt off the machine.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(request, timeout=timeout) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            raise DeskThreadError(ErrorCode.MODEL_UNAVAILABLE) from exc

    def available(self) -> bool:
        try:
            self._call("/api/version", timeout=2)
        except DeskThreadError:
            return False
        return True

    def verify_pin(self) -> str:
        """The digest of the installed model must equal the pinned one (FT-45)."""
        models = self._call("/api/tags", timeout=10).get("models", [])
        digest = next(
            (m.get("digest", "") for m in models if m.get("name") == config.MODEL_TAG), ""
        )
        if digest != config.MODEL_DIGEST:
            raise DeskThreadError(ErrorCode.MODEL_NOT_PINNED)
        self._pinned = True
        return digest

    def complete(self, prompt: str, images: list[bytes] | None = None) -> str:
        if not self._pinned:
            self.verify_pin()
        message: dict[str, Any] = {"role": "user", "content": prompt}
        if images:
            message["images"] = [base64.b64encode(i).decode() for i in images]
        body = {
            "model": config.MODEL_TAG,
            "messages": [message],
            "stream": False,
            "think": False,
            "keep_alive": config.MODEL_KEEP_ALIVE,
            "options": {"temperature": 0, "seed": config.MODEL_SEED},
        }
        self.calls += 1
        reply = self._call("/api/chat", body)
        try:
            return str(reply["message"]["content"])
        except (KeyError, TypeError) as exc:
            raise DeskThreadError(ErrorCode.MODEL_BAD_OUTPUT) from exc

    def loaded(self) -> bool:
        try:
            models = self._call("/api/ps", timeout=5).get("models", [])
        except DeskThreadError:
            return False
        return any(m.get("name") == config.MODEL_TAG for m in models)

    def unload(self) -> bool:
        """Forget now: ask the runtime to drop the model, and with it the last prompt."""
        try:
            self._call("/api/generate", {"model": config.MODEL_TAG, "keep_alive": 0}, timeout=30)
        except DeskThreadError:
            return not self.loaded()
        for _ in range(20):
            if not self.loaded():
                return True
            time.sleep(0.25)
        return False


class ModelServer:
    """Our own `ollama serve`, started as a child on 127.0.0.1 and stopped at End session."""

    def __init__(self) -> None:
        self._process: subprocess.Popen[bytes] | None = None

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process else None

    def start(self, gateway: ModelGateway, wait_s: float = 20) -> bool:
        """True when a server answers. Does nothing if one is already there on our port."""
        if gateway.available():
            return True
        binary = shutil.which("ollama")
        if binary is None:
            return False
        self._process = subprocess.Popen(
            [binary, "serve"],
            env={**os.environ, **config.QUIET_ENV},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,  # the runtime's log can hold prompt text: never kept
        )
        deadline = time.monotonic() + wait_s
        while time.monotonic() < deadline:
            if gateway.available():
                return True
            time.sleep(0.25)
        return False

    def stop(self) -> None:
        if self._process is None:
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=5)
        self._process = None
