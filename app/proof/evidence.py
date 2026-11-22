"""The Proof panel (FT-17, FT-18, FT-19, FT-22): evidence a user can compare with the
Mac's own tools, and a plain statement of what it cannot prove.

- Connections: the open connections of our processes, sampled with `lsof` when asked.
  A sample can miss a connection that opened and closed in between; the limits say so.
- Folder fingerprint: names, sizes and modification times of every file under the chosen
  folder, at the moment it was chosen and now. No file is opened to compute it, so
  off-limits files are covered without being read.
- Writes: a Python audit hook counts every file this backend opens for writing. The design
  target is zero; the panel shows the real count.
"""

import hashlib
import os
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI

from app import config
from app.clock import now
from app.proof.processes import watched
from app.runtime import Runtime
from contracts.api import Connection, FolderHash, Proof

LIMITS = (
    "This covers DeskThread's own programs only, not other apps on this Mac. Connections are "
    "sampled when you open this panel, so a very short one could be missed; turning Wi-Fi off "
    "is the stronger check. The fingerprint covers file names, sizes and times, not content. "
    "It cannot prove that memory was erased: freed memory, swap and sleep images belong to "
    "the operating system. A quote from an image matches the model's reading, not the pixels."
)
LOCAL_HOSTS = ("127.0.0.1", "[::1]", "localhost")
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
_writes: list[int] = [0]
_installed: list[bool] = [False]


def _audit(event: str, args: tuple[object, ...]) -> None:
    if event != "open" or len(args) < 3:
        return
    path, mode, flags = args[0], args[1], args[2]
    writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
        isinstance(flags, int) and bool(flags & _WRITE_FLAGS)
    )
    if writing and isinstance(path, (str, bytes, os.PathLike)) and os.fspath(path) != os.devnull:
        _writes[0] += 1


def install_write_audit() -> None:
    """Count every file opened for writing from now on. Called once at launch."""
    if not _installed[0]:
        sys.addaudithook(_audit)
        _installed[0] = True


def files_written() -> int:
    return _writes[0]


def fingerprint(root: Path) -> tuple[str, int]:
    """A hash of every file's name, size and modification time. Opens no file."""
    digest, count = hashlib.sha256(), 0
    for folder, _dirs, names in sorted(os.walk(root)):
        for name in sorted(names):
            path = Path(folder) / name
            try:
                info = path.lstat()
            except OSError:
                continue
            rel = path.relative_to(root).as_posix()
            digest.update(f"{rel}\0{info.st_size}\0{info.st_mtime_ns}\n".encode())
            count += 1
    return digest.hexdigest(), count


def parse_lsof(text: str, names: dict[int, str]) -> list[Connection]:
    """Connections from `lsof -nP -iTCP` output. A listener counts by the address it binds."""
    found = []
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 9 or not parts[1].isdigit():
            continue
        pid, name = int(parts[1]), parts[8]
        remote = name.split("->")[-1]
        host = remote.rsplit(":", 1)[0]
        found.append(
            Connection(
                process=names.get(pid, parts[0]),
                pid=pid,
                remote=remote + (" (listening)" if "->" not in name else ""),
                local_only=host in LOCAL_HOSTS,  # "*" would mean reachable from outside
            )
        )
    return found


def connections(pids: dict[int, str]) -> list[Connection]:
    if not pids:
        return []
    done = subprocess.run(
        ["/usr/sbin/lsof", "-nP", "-iTCP", "-a", "-p", ",".join(str(p) for p in pids)],
        capture_output=True,
        text=True,
        check=False,
    )
    return parse_lsof(done.stdout, pids)


class Evidence:
    """Remembers the fingerprint of each chosen folder, in memory, to compare later."""

    def __init__(self, runtime: Runtime) -> None:
        self._runtime = runtime
        self._before: dict[Path, tuple[str, int]] = {}
        runtime.on_folder.append(self.remember)

    def remember(self, roots: list[Path]) -> None:
        """Keep the fingerprint taken when each folder was first chosen; drop removed ones."""
        self._before = {r: self._before.get(r) or fingerprint(r) for r in roots}

    def folders(self) -> tuple[FolderHash, ...]:
        out = []
        for root, (before, _count) in self._before.items():
            current, count = fingerprint(root)
            out.append(
                FolderHash(
                    label=root.name,
                    files=count,
                    before=before[:16],
                    now=current[:16],
                    unchanged=before == current,
                )
            )
        return tuple(out)

    def proof(self) -> Proof:
        runtime = self._runtime
        processes = watched(runtime.server.pid if runtime.server else None)
        found = connections({p.pid: p.name for p in processes})
        session = runtime.session
        return Proof(
            sampled_at=now(),
            connections=tuple(found),
            all_local=all(c.local_only for c in found),
            folders=self.folders(),
            files_written_by_app=files_written(),
            telemetry_off={name: os.environ.get(name) == value for name, value in SWITCHES.items()},
            audit=tuple(session.broker.audit()[-50:]) if session else (),
            limits=LIMITS,
        )


# Switches the launcher sets for itself and for the model server (N-5).
SWITCHES = {
    k: v for k, v in config.QUIET_ENV.items() if k not in {"OLLAMA_HOST", "OLLAMA_KEEP_ALIVE"}
}


def register(app: FastAPI, runtime: Runtime) -> Evidence:
    evidence = Evidence(runtime)

    @app.get("/api/proof")
    def proof() -> Proof:
        return evidence.proof()

    return evidence
