"""Take the user to one item in its own Mac app, when they press the button in the viewer.

These scripts are kept apart from the read scripts in `mac.py` on purpose. A read script
may only fetch. A script here may only bring an app to the front and make it display one
thing ("activate", "show", "view calendar at"): it changes what the app shows on screen,
never what the app holds. A test checks both sets separately.
"""

import subprocess
from datetime import datetime

SHOW: dict[str, str] = {
    # The note itself, by the id the Notes app gave it.
    "mac:notes": """
on run argv
    tell application "Notes"
        activate
        show note id (item 1 of argv)
    end tell
end run
""",
    # The reminder itself, by its id.
    "mac:reminders": """
on run argv
    tell application "Reminders"
        activate
        show (first reminder whose id is (item 1 of argv))
    end tell
end run
""",
    # The day of the entry, in day view. (Calendar has no quick way to one entry by id.)
    "mac:calendar": """
on run argv
    set d to current date
    set day of d to 1
    set year of d to (item 1 of argv) as integer
    set month of d to (item 2 of argv) as integer
    set day of d to (item 3 of argv) as integer
    set time of d to 12 * hours
    tell application "Calendar"
        activate
        switch view to day view
        view calendar at d
    end tell
end run
""",
}


def show_in_app(source_id: str, meta: dict[str, str], date: datetime | None) -> bool:
    """Display the item in its app. False when there is no way to point at it (then the
    caller just opens the app)."""
    script = SHOW.get(source_id)
    if script is None:
        return False
    if source_id == "mac:calendar":
        if date is None:
            return False
        local = date.astimezone()
        args = [str(local.year), str(local.month), str(local.day)]
    else:
        if not meta.get("uid"):
            return False
        args = [meta["uid"]]
    try:
        done = subprocess.run(
            ["/usr/bin/osascript", "-e", script, *args],
            check=False,
            capture_output=True,
            timeout=20,
        )
    except subprocess.TimeoutExpired:
        return False
    return done.returncode == 0
