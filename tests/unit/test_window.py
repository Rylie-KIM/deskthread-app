"""The native window launcher (FT-24): the parts that can be tested without opening a window."""

import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

pytest.importorskip("WebKit")  # macOS only

from app import window
from app.__main__ import prepare
from contracts.api import TOKEN_HEADER

REPO = Path(__file__).resolve().parents[2]


def _status(address: str, token: str) -> int:
    request = urllib.request.Request(address, headers={TOKEN_HEADER: token})  # noqa: S310
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=5) as response:
        return int(response.status)


def test_the_backend_runs_beside_the_window_and_closing_it_ends_the_session() -> None:
    launch = prepare(model_server=False)
    assert launch is not None and launch.address.startswith("http://127.0.0.1:")
    backend = window.serve(launch)
    assert launch.web.started and threading.current_thread() is not backend
    url = f"{launch.runtime.origin}/api/session"
    assert _status(url, launch.runtime.token) == 200

    window.end_session(launch)  # what closing the window does
    backend.join(timeout=10)
    assert not backend.is_alive()
    with pytest.raises((urllib.error.URLError, ConnectionError)):
        _status(url, launch.runtime.token)
    window.end_session(launch)  # a second call is harmless


def test_the_web_view_keeps_nothing_on_disk_and_no_browser_is_started() -> None:
    source = (REPO / "app" / "window.py").read_text()
    assert "nonPersistentDataStore()" in source
    assert (
        "webbrowser" not in source and "Google Chrome" not in source and "subprocess" not in source
    )


def test_the_page_can_ask_the_window_for_two_things_only() -> None:
    restarted: list[bool] = []
    bridge = window.Bridge.alloc().init()
    bridge.on_restart = lambda: restarted.append(True)

    class Message:
        def __init__(self, text: str) -> None:
            self.text = text

        def body(self) -> str:
            return self.text

    for text in ("restart", "delete everything", "open https://example.com", ""):
        bridge.userContentController_didReceiveScriptMessage_(None, Message(text))
    assert restarted == [True]  # only "restart" did anything; unknown requests are ignored
