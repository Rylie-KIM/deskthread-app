"""Start DeskThread: `python -B -m app` (the launcher DeskThread.command does this).

Starts our own model server and the backend, both on 127.0.0.1, and opens the page.
Nothing is written to disk: no settings, no log file, no bytecode. End session in the page
(or Ctrl+C here) stops both programs.
"""

import argparse
import os
import socket
import sys
import webbrowser
from pathlib import Path

sys.dont_write_bytecode = True

import uvicorn  # noqa: E402

from app import config  # noqa: E402
from app.api import create_app  # noqa: E402
from app.model import ModelGateway, ModelServer  # noqa: E402
from app.proof.evidence import install_write_audit  # noqa: E402
from app.runtime import Runtime  # noqa: E402

UI_DIR = Path(__file__).resolve().parent.parent / "ui" / "out"


def free_port() -> int:
    """A random free port on the loopback address, chosen by the operating system."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((config.LOOPBACK, 0))
        return int(probe.getsockname()[1])


def main() -> int:
    parser = argparse.ArgumentParser(description="DeskThread")
    parser.add_argument("--port", type=int, default=0, help="default: a random free port")
    parser.add_argument("--no-browser", action="store_true", help="do not open the page")
    parser.add_argument("--no-model-server", action="store_true", help="for tests")
    args = parser.parse_args()

    os.environ.update(config.QUIET_ENV)  # telemetry and cloud features off, for us and children
    install_write_audit()  # count every file this backend opens for writing

    gateway = ModelGateway()
    server = None if args.no_model_server else ModelServer()
    if server is not None and not server.start(gateway):
        print("The local model server did not start. Is Ollama installed (brew install ollama)?")
        return 2

    port = args.port or free_port()
    runtime = Runtime(gateway, port, gateway=gateway, server=server)
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

    address = f"{runtime.origin}/#t={runtime.token}"
    print(f"DeskThread is running on this Mac only.\nOpen: {address}", flush=True)
    if not UI_DIR.is_dir():
        print("The page is not built yet (ui/out is missing): run `make ui` once.", flush=True)
    if not args.no_browser:
        webbrowser.open(address)
    try:
        web.run()
    finally:
        if server is not None:
            gateway.unload()
            server.stop()
    print("DeskThread has stopped. Nothing is listening any more.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
