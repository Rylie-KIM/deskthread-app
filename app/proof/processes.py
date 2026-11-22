"""The programs that make up a running DeskThread, with their memory, from the OS itself.

The numbers come from `ps`, the same source Activity Monitor uses, so a user can compare.
"""

import os
import subprocess

from app import config
from contracts.api import ProcessInfo

BACKEND, SERVER, RUNNER = "DeskThread backend", "Model server", "Model runner"


def _table() -> list[tuple[int, int, int]]:
    """(pid, parent pid, resident memory in KB) for every process."""
    done = subprocess.run(
        ["/bin/ps", "-axo", "pid=,ppid=,rss="], capture_output=True, text=True, check=False
    )
    rows = []
    for line in done.stdout.splitlines():
        parts = line.split()
        if len(parts) == 3 and all(p.isdigit() for p in parts):
            rows.append((int(parts[0]), int(parts[1]), int(parts[2])))
    return rows


def mac_memory() -> tuple[float, float]:
    """(all memory of this Mac, memory still available now), in MB, asked from the system
    each time: nothing here is a fixed number. Available = free + inactive + speculative +
    purgeable pages, as the Mac's own `vm_stat` reports them."""
    total = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 1048576
    done = subprocess.run(["/usr/bin/vm_stat"], capture_output=True, text=True, check=False)
    page, pages = 16384, 0
    for line in done.stdout.splitlines():
        name, _, value = line.partition(":")
        if "page size of" in line:
            digits = "".join(c for c in line.split("page size of")[1] if c.isdigit())
            page = int(digits) if digits else page
        elif name.strip() in (
            "Pages free",
            "Pages inactive",
            "Pages speculative",
            "Pages purgeable",
        ):
            number = value.strip().rstrip(".")
            pages += int(number) if number.isdigit() else 0
    return round(total), round(pages * page / 1048576)


def listener_pid(port: int = config.MODEL_PORT) -> int | None:
    """The process listening on a local port, or None."""
    done = subprocess.run(
        ["/usr/sbin/lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
        capture_output=True,
        text=True,
        check=False,
    )
    first = done.stdout.split()
    return int(first[0]) if first and first[0].isdigit() else None


def watched(server_pid: int | None) -> list[ProcessInfo]:
    """This backend, the model server and the model runners it started."""
    table = _table()
    rss = {pid: kb for pid, _, kb in table}
    server_pid = server_pid or listener_pid()
    found = [(BACKEND, os.getpid())]
    if server_pid in rss:
        found.append((SERVER, server_pid))
        children, frontier = [], [server_pid]
        while frontier:
            parent = frontier.pop()
            kids = [pid for pid, ppid, _ in table if ppid == parent]
            children += kids
            frontier += kids
        found += [(RUNNER, pid) for pid in sorted(children)]
    return [
        ProcessInfo(name=name, pid=pid, memory_mb=round(rss.get(pid, 0) / 1024, 1))
        for name, pid in found
    ]
