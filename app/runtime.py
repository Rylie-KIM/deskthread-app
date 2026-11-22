"""The running session's state: the token, the chosen folder, and the parts built on it.

Held in memory only. Nothing here is saved: a new launch starts with no folder chosen and
every source Off (R4, R15).
"""

import secrets
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path

from app.model import Model, ModelGateway, ModelServer
from app.session import Session, choose_folder, new_session, remove_folder
from contracts.adapters import SourceAdapter
from contracts.errors import DeskThreadError, ErrorCode

DEMO_MARKER = ".deskthread-demo"
CHOOSE_FOLDER = 'POSIX path of (choose folder with prompt "Choose the folder DeskThread may read")'


class Runtime:
    def __init__(
        self,
        model: Model,
        port: int,
        gateway: ModelGateway | None = None,
        server: ModelServer | None = None,
        demo_folder: Path | None = None,
        apps: list[SourceAdapter] | None = None,
    ) -> None:
        self.model, self.port, self.gateway, self.server = model, port, gateway, server
        # Offered on the first screen only if it is a folder our generator built.
        self.demo_folder = (
            demo_folder if demo_folder and (demo_folder / DEMO_MARKER).is_file() else None
        )
        # A fresh random token for each launch; the page gets it in the address fragment,
        # which a browser never sends over the network (FT-23).
        self.token = secrets.token_urlsafe(32)
        # One session per launch. Apps on this Mac are listed from the start, all Off.
        self.session: Session = new_session(model, apps)
        self.ask_lock = threading.Lock()  # one question at a time; revoke never waits on it
        self.on_folder: list[Callable[[list[Path]], None]] = []  # told the folders in use
        self.stop: Callable[[], None] = lambda: None  # set by the launcher: quits the server

    @property
    def origin(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def require(self) -> Session:
        return self.session

    def choose(self, path: str) -> Session:
        """Add a folder. An empty path opens the Mac's own folder dialog (FT-33)."""
        folder = Path(path).expanduser() if path else self._dialog()
        if not folder.is_dir():
            raise DeskThreadError(ErrorCode.BAD_REQUEST, "that folder does not exist")
        choose_folder(self.session, folder.resolve())
        self._told()
        return self.session

    def remove(self, path: str) -> Session:
        """Stop using a folder: its sources are revoked and leave memory."""
        remove_folder(self.session, Path(path).expanduser())
        self._told()
        return self.session

    @property
    def folders(self) -> list[Path]:
        return self.session.policy.roots

    def _told(self) -> None:
        for callback in self.on_folder:
            callback(self.folders)

    @staticmethod
    def _dialog() -> Path:
        done = subprocess.run(
            ["/usr/bin/osascript", "-e", CHOOSE_FOLDER],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if done.returncode != 0 or not done.stdout.strip():
            raise DeskThreadError(ErrorCode.BAD_REQUEST, "no folder was chosen")
        return Path(done.stdout.strip())
