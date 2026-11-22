"""Gate G3, the local model gateway (FT-09): the only code that talks to the model.

It is also the only module in app/ allowed to open a network connection, and it refuses any
address that is not 127.0.0.1 (a test checks both). The model has no tools: it gets text and
images and returns text, which is only ever displayed or parsed, never executed (FT-44).
"""

import base64
import contextlib
import http.client
import json
import os
import shutil
import signal
import socket
import subprocess
import threading
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
        except DeskThreadError as err:
            # Only a reply that is not JSON is asked for again; a model that is gone, or a
            # request that was stopped by the user, is not.
            if err.code is not ErrorCode.MODEL_BAD_OUTPUT or attempt == tries - 1:
                raise
    raise DeskThreadError(ErrorCode.MODEL_BAD_OUTPUT)


class ModelGateway:
    def __init__(self, base_url: str = f"http://{config.LOOPBACK}:{config.MODEL_PORT}") -> None:
        parsed = urlparse(base_url)
        if parsed.scheme != "http" or parsed.hostname != config.LOOPBACK:
            # Not "localhost" either: a name can be pointed somewhere else.
            raise DeskThreadError(ErrorCode.MODEL_UNAVAILABLE, "the model must be on 127.0.0.1")
        self._base = base_url.rstrip("/")
        self._host, self._port = parsed.hostname or config.LOOPBACK, parsed.port or 80
        self._lock = threading.Lock()
        self._inflight: set[http.client.HTTPConnection] = set()
        self._pinned = False
        self.calls = 0
        self.tag = config.MODEL_TAG  # the model in use; the user may choose another
        self.digest = ""  # the digest of the model in use, once checked
        # True for a launch without our own model server (tests, screenshots): such a launch
        # must never look at or unload the models of a server another session is using.
        self.detached = False
        self._search: bool | None = None  # is the search model on this Mac? asked once

    @property
    def reads_pictures(self) -> bool:
        choice = config.model_choice(self.tag)
        return choice.reads_pictures if choice else False

    def _call(self, path: str, body: dict[str, Any] | None = None, timeout: float = 300) -> Any:
        """One request to the model server on this Mac. It is made with http.client (never
        through a proxy, which would carry the prompt off the machine), and its connection
        is remembered while it runs so that `abort` can cut it off."""
        data = json.dumps(body).encode() if body is not None else None
        conn = http.client.HTTPConnection(self._host, self._port, timeout=timeout)
        with self._lock:
            self._inflight.add(conn)
        try:
            headers = {"Content-Type": "application/json"} if data is not None else {}
            conn.request("POST" if data is not None else "GET", path, body=data, headers=headers)
            response = conn.getresponse()
            if response.status >= 400:
                raise DeskThreadError(ErrorCode.MODEL_UNAVAILABLE)
            return json.load(response)
        except (http.client.HTTPException, TimeoutError, ValueError, OSError) as exc:
            raise DeskThreadError(ErrorCode.MODEL_UNAVAILABLE) from exc
        finally:
            with self._lock:
                self._inflight.discard(conn)
            conn.close()

    def abort(self) -> None:
        """Cut off every request that is running (the user pressed Stop). The model server
        stops generating when its client goes away; the caller gets MODEL_UNAVAILABLE."""
        with self._lock:
            running = list(self._inflight)
        for conn in running:
            try:
                if conn.sock is not None:
                    conn.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass  # already finished

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
        if not config.approved(tag):
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
        self._search = None  # a download may have brought the search model

    def embed(self, texts: list[str]) -> list[list[float]] | None:
        """Texts as lists of numbers, from the search model on this Mac. None when that
        model is not on this Mac (meaning search is then off)."""
        tag = config.SEARCH_MODEL.tag
        if self.detached:
            return None
        if self._search is None:
            self._search = tag in self.installed()
        if not self._search:
            return None
        body = {"model": tag, "input": texts, "keep_alive": config.MODEL_KEEP_ALIVE}
        reply = self._call("/api/embed", body, timeout=180)
        made = reply.get("embeddings") if isinstance(reply, dict) else None
        return made if isinstance(made, list) else None

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
        if self.detached:
            return []
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
