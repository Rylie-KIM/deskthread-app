"""Gate G3, the local model gateway (FT-09): the only code that talks to the model.

It is also the only module in app/ allowed to open a network connection, and it refuses any
address that is not 127.0.0.1 (a test checks both). The model has no tools: it gets text and
images and returns text, which is only ever displayed or parsed, never executed (FT-44).
"""

import base64
import contextlib
import json
import os
import shutil
import signal
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable
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
        self.tag = config.MODEL_TAG  # the model in use; the user may choose another
        self.digest = ""  # the digest of the model in use, once checked

    @property
    def reads_pictures(self) -> bool:
        choice = config.model_choice(self.tag)
        return choice.reads_pictures if choice else False

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

    def installed(self) -> dict[str, str]:
        """Models on this Mac: tag -> digest."""
        models = self._call("/api/tags", timeout=10).get("models", [])
        return {str(m.get("name", "")): str(m.get("digest", "")) for m in models}

    def verify_pin(self) -> str:
        """The model in use must be on the approved list, installed, and (where DeskThread
        has tested it) have exactly the tested digest (FT-45)."""
        choice = config.model_choice(self.tag)
        digest = self.installed().get(self.tag, "")
        if choice is None or not digest or (choice.digest and digest != choice.digest):
            raise DeskThreadError(ErrorCode.MODEL_NOT_PINNED)
        self._pinned, self.digest = True, digest
        return digest

    def select(self, tag: str) -> None:
        """Use another approved model that is already on this Mac."""
        if config.model_choice(tag) is None:
            raise DeskThreadError(ErrorCode.BAD_REQUEST, "not an approved model")
        if tag not in self.installed():
            raise DeskThreadError(ErrorCode.MODEL_UNAVAILABLE, "download this model first")
        if tag != self.tag:
            self.unload()  # the old model, and the last prompt it held, leave memory
        self.tag, self._pinned, self.digest = tag, False, ""
        self.verify_pin()

    def pull(self, tag: str, progress: Callable[[int], None]) -> None:
        """Download an approved model. This is the model server using the internet, on the
        user's click: the one moment anything of DeskThread reaches outside this Mac."""
        if config.model_choice(tag) is None:
            raise DeskThreadError(ErrorCode.BAD_REQUEST, "not an approved model")
        body = json.dumps({"model": tag, "stream": True}).encode()
        request = urllib.request.Request(self._base + "/api/pull", data=body)  # noqa: S310
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(request, timeout=3600) as response:
                for line in response:
                    step = json.loads(line or b"{}")
                    if step.get("error"):
                        raise DeskThreadError(ErrorCode.MODEL_UNAVAILABLE, "the download failed")
                    total, done = step.get("total"), step.get("completed")
                    if total and done is not None:
                        progress(min(99, int(100 * done / total)))
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            raise DeskThreadError(ErrorCode.MODEL_UNAVAILABLE, "the download failed") from exc
        progress(100)

    def complete(self, prompt: str, images: list[bytes] | None = None) -> str:
        if not self._pinned:
            self.verify_pin()
        message: dict[str, Any] = {"role": "user", "content": prompt}
        if images:
            message["images"] = [base64.b64encode(i).decode() for i in images]
        body = {
            "model": self.tag,
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

    def _held(self) -> list[str]:
        """Names of the models our server has in memory right now."""
        try:
            models = self._call("/api/ps", timeout=5).get("models", [])
        except DeskThreadError:
            return []
        return [str(m.get("name")) for m in models]

    def loaded(self) -> bool:
        return bool(self._held())

    def unload(self, wait_s: float = 20) -> bool:
        """Ask the runtime to drop every model it holds, and with it the last prompt, then
        wait until none is left. Returns whether memory is really free of them."""
        for tag in self._held():
            try:
                self._call("/api/generate", {"model": tag, "keep_alive": 0}, timeout=30)
            except DeskThreadError:
                continue
        end = time.monotonic() + wait_s
        while time.monotonic() < end:
            if not self._held():
                return True
            time.sleep(0.25)
        return not self._held()


class ModelServer:
    """Our own `ollama serve` on 127.0.0.1 and our own port, stopped at End session.

    If a server is already listening on our port (left over from a launch that was killed),
    it is adopted: the port is ours alone, so End session stops that one too.
    """

    def __init__(self) -> None:
        self._process: subprocess.Popen[bytes] | None = None
        self._adopted: int | None = None

    @property
    def pid(self) -> int | None:
        return self._process.pid if self._process else self._adopted

    @staticmethod
    def _listener() -> int | None:
        done = subprocess.run(
            ["/usr/sbin/lsof", "-nP", f"-iTCP:{config.MODEL_PORT}", "-sTCP:LISTEN", "-t"],
            capture_output=True,
            text=True,
            check=False,
        )
        first = done.stdout.split()
        return int(first[0]) if first and first[0].isdigit() else None

    def start(self, gateway: ModelGateway, wait_s: float = 20) -> bool:
        """True when a server answers on our port."""
        if gateway.available():
            self._adopted = self._listener()
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
        if self._process is not None:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
            self._process = None
        elif self._adopted is not None:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.kill(self._adopted, signal.SIGTERM)
            self._adopted = None
