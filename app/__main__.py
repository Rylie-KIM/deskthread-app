"""Start DeskThread: `python -B -m app` (the launcher DeskThread.command does this).

Starts our own model server and the backend, both on 127.0.0.1, and opens the page.
Nothing is written to disk: no settings, no log file, no bytecode. End session in the page
(or Ctrl+C here) stops both programs.
"""

import argparse
import os
import socket
import subprocess
import sys
import webbrowser
from dataclasses import dataclass
from pathlib import Path

sys.dont_write_bytecode = True

import uvicorn  # noqa: E402

from app import config  # noqa: E402
from app.api import create_app  # noqa: E402
from app.model import ModelGateway, ModelServer  # noqa: E402
from app.proof.evidence import install_write_audit  # noqa: E402
from app.runtime import Runtime  # noqa: E402
from app.sources.mac import mac_apps  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
UI_DIR = REPO / "ui" / "out"
CHROME = Path("/Applications/Google Chrome.app")


def free_port() -> int:
    """A random free port on the loopback address, chosen by the operating system."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((config.LOOPBACK, 0))
        return int(probe.getsockname()[1])


def open_page(address: str, own_window: bool) -> None:
    """Open the page. With --window and Chrome installed it gets its own window without
    tabs or an address bar, like an app; otherwise the default browser opens it."""
    if own_window and CHROME.is_dir():
        done = subprocess.run(
            ["/usr/bin/open", "-na", str(CHROME), "--args", f"--app={address}"], check=False
        )
        if done.returncode == 0:
            return
    webbrowser.open(address)


@dataclass
class Launch:
    """Everything a start needs: the session state, the web server and the page address."""

    runtime: Runtime
    web: uvicorn.Server
    gateway: ModelGateway
    server: ModelServer | None

    @property
    def address(self) -> str:
        return f"{self.runtime.origin}/#t={self.runtime.token}"

    def stop_model(self) -> None:
        if self.server is not None:
            self.gateway.unload()
            self.server.stop()


def prepare(port: int = 0, model_server: bool = True, mac: bool = True) -> Launch | None:
    """Start the model server and build the backend. None if the model server is missing."""
    os.environ.update(config.QUIET_ENV)  # telemetry and cloud features off, for us and children
    install_write_audit()  # count every file this backend opens for writing

    gateway = ModelGateway()
    server = ModelServer() if model_server else None
    if server is not None and not server.start(gateway):
        return None

    port = port or free_port()
    runtime = Runtime(
        gateway,
        port,
        gateway=gateway,
        server=server,
        demo_folder=REPO / "demo-laptop",
        apps=list(mac_apps()) if mac else [],
    )
    web = uvicorn.Server(
        uvicorn.Config(
            create_app(runtime, UI_DIR),
            host=config.LOOPBACK,  # never 0.0.0.0: nothing outside this Mac can reach it
            port=port,
            log_level="warning",
            access_log=False,  # no request lines: an address can carry the session token
        )
    )
    runtime.stop = lambda: setattr(web, "should_exit", True)
    return Launch(runtime, web, gateway, server)


def main() -> int:
    parser = argparse.ArgumentParser(description="DeskThread")
    parser.add_argument("--port", type=int, default=0, help="default: a random free port")
    parser.add_argument("--no-browser", action="store_true", help="do not open the page")
    parser.add_argument("--no-model-server", action="store_true", help="for tests")
    parser.add_argument("--window", action="store_true", help="open as its own window")
    args = parser.parse_args()

    launch = prepare(args.port, not args.no_model_server)
    if launch is None:
        print("The local model server did not start. Is Ollama installed (brew install ollama)?")
        return 2
    print(f"DeskThread is running on this Mac only.\nOpen: {launch.address}", flush=True)
    if not UI_DIR.is_dir():
        print("The page is not built yet (ui/out is missing): run `make ui` once.", flush=True)
    if not args.no_browser:
        open_page(launch.address, args.window)
    try:
        launch.web.run()
    finally:
        launch.stop_model()
    print("DeskThread has stopped. Nothing is listening any more.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
