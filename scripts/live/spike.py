"""Feasibility spikes against the real Mac apps (tasks T-05, T-33, T-06, T-07).

Read-only. Prints counts, durations and pass/fail only, through the redaction guard (R1):
no title, name or text from any app is ever printed. Run one source at a time:

    uv run python -m scripts.live.spike calendar|reminders|notes|mail

macOS asks once per app whether this terminal may control it. That permission is "control",
not "read only"; the scripts below only count things.
"""

import subprocess
import sys
import time

from contracts.errors import DeskThreadError, ErrorCode
from contracts.redact import live_print, safe_error

TIMEOUT_S = 120

# Each script returns integers separated by spaces. Nothing else may come back.
SCRIPTS: dict[str, tuple[tuple[str, ...], str]] = {
    "calendar": (
        ("calendars", "events"),
        """
        with timeout of 100 seconds
            tell application "Calendar"
                set d1 to current date
                set d2 to d1 + 2 * days
                set total to 0
                repeat with c in calendars
                    set total to total + (count (every event of c ¬
                        whose start date ≥ d1 and start date ≤ d2))
                end repeat
                return ((count calendars) as text) & " " & (total as text)
            end tell
        end timeout
        """,
    ),
    "reminders": (
        ("lists", "items"),
        """
        with timeout of 100 seconds
            tell application "Reminders"
                return ((count lists) as text) & " " & ¬
                    ((count (reminders whose completed is false)) as text)
            end tell
        end timeout
        """,
    ),
    "notes": (
        ("folders", "items", "locked"),
        """
        with timeout of 100 seconds
            tell application "Notes"
                return ((count folders) as text) & " " & ((count notes) as text) & " " & ¬
                    ((count (notes whose password protected is true)) as text)
            end tell
        end timeout
        """,
    ),
    "mail": (
        ("mailboxes", "messages"),
        """
        with timeout of 100 seconds
            tell application "Mail"
                return ((count mailboxes) as text) & " " & ((count messages of inbox) as text)
            end tell
        end timeout
        """,
    ),
}


def run(source: str) -> int:
    names, script = SCRIPTS[source]
    started = time.monotonic()
    try:
        done = subprocess.run(
            ["/usr/bin/osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
            check=False,
        )
        if done.returncode != 0:
            # stderr can name apps or content: keep only the code class.
            missing = "-1743" in done.stderr or "-1744" in done.stderr
            code = ErrorCode.OS_PERMISSION_MISSING if missing else ErrorCode.READ_FAILED
            raise DeskThreadError(code)
        counts = [int(part) for part in done.stdout.split()]
        if len(counts) != len(names):
            raise DeskThreadError(ErrorCode.READ_FAILED)
    except subprocess.TimeoutExpired:
        live_print(f"{source}: timeout fail")
        return 1
    except (DeskThreadError, ValueError) as exc:
        live_print(f"{source}: {safe_error(exc)} fail")
        return 1
    seconds = time.monotonic() - started
    report = " ".join(f"{n}={c}" for n, c in zip(names, counts, strict=True))
    live_print(f"{source}: {report} writes=0 seconds={seconds:.1f} pass")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in SCRIPTS:
        live_print("error code=E-504")
        sys.exit(2)
    sys.exit(run(sys.argv[1]))
