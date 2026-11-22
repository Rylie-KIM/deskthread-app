"""N-6 and the launcher (FT-24, FT-16): the real server process starts on 127.0.0.1 only,
answers only with the token, and after End session nothing is listening."""

import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from contracts.api import TOKEN_HEADER

REPO = Path(__file__).resolve().parents[2]


def _call(url: str, token: str = "", method: str = "GET") -> tuple[int, dict[str, object]]:
    request = urllib.request.Request(url, method=method, headers={TOKEN_HEADER: token})  # noqa: S310
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=10) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as err:
        return err.code, json.load(err)


def test_n6_launch_serve_end_session_and_then_nothing_listens() -> None:
    process = subprocess.Popen(
        [sys.executable, "-B", "-m", "app", "--no-browser", "--no-model-server"],
        cwd=REPO,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert process.stdout is not None
        banner = process.stdout.readline() + process.stdout.readline()
        match = re.search(r"Open: (http://127\.0\.0\.1:(\d+))/#t=(\S+)", banner)
        assert match, banner
        origin, port, token = match[1], match[2], match[3]

        for _ in range(100):  # wait until it answers
            try:
                status, _body = _call(f"{origin}/api/session", token)
                break
            except (urllib.error.URLError, ConnectionError):
                process.poll()
                assert process.returncode is None, "the server exited early"
                __import__("time").sleep(0.1)
        assert status == 200
        assert _call(f"{origin}/api/session")[0] == 401  # no token, no answer

        listening = subprocess.run(
            ["/usr/sbin/lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        assert f"127.0.0.1:{port}" in listening and "*:" not in listening  # loopback only

        status, receipt = _call(f"{origin}/api/end-session", token, method="POST")
        assert status == 200 and receipt["memory_cleared"] is True
        assert receipt["files_written_by_app"] == 0  # the backend wrote no file at all
        assert process.wait(timeout=15) == 0
        with pytest.raises((urllib.error.URLError, ConnectionError)):
            _call(f"{origin}/api/session", token)  # the address refuses: the server is gone
    finally:
        if process.poll() is None:
            process.kill()
