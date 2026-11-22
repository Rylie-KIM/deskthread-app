"""Connectors to the Mac's own apps: Calendar, Notes, Reminders and Mail (FT-48 to FT-52).

They read the data where it already lives, through each app's scripting interface, so no
exported second copy is needed. Every script below only reads: it counts and gets values,
and never makes, changes, sends, moves or deletes anything. A test scans the scripts for
write commands (dev rule R2).

macOS asks the user once per app whether DeskThread may "control" it. That wording is the
operating system's and is broader than what happens here: only the read commands below are
ever sent. Names chosen by the user (a calendar, a folder, a list, a mailbox) are passed as
arguments, never pasted into a script.
"""

import atexit
import subprocess
import threading
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app import period
from app.clock import now
from app.readers.common import find_date, item_id, to_units
from contracts.adapters import OsPermission, ReadGrant, Scope, SourceAdapter
from contracts.errors import DeskThreadError, ErrorCode
from contracts.items import Item, ItemKind, SourceKind, Uncounted

FS, RS = "\x1f", "\x1e"  # field and record separators in what a script returns
Runner = Callable[[str, list[str], float], str]

# Variable names in the scripts start with "got": AppleScript reads a plain plural such as
# "dates" as "every date" and then refuses the assignment (error -10006).
_HEAD = """
on txt(v)
    if v is missing value then return ""
    return v as text
end txt
on stamp(d)
    if d is missing value then return ""
    return (d as «class isot» as string)
end stamp
on run argv
    set FS to character id 31
    set RS to character id 30
    set out to ""
"""
_TAIL = """
    return out
end run
"""

SCRIPTS: dict[str, str] = {
    # ---------------------------------------------------------------- Calendar
    "calendar.list": _HEAD
    + """
    tell application "Calendar"
        set gotNames to name of calendars
    end tell
    repeat with n in gotNames
        set out to out & (n as text) & FS & "" & RS
    end repeat
"""
    + _TAIL,
    # The slow route (used only when the calendar framework is refused): one request for all
    # titles and one for all start times of a calendar, never one request per event.
    "calendar.read": _HEAD
    + """
    set d1 to (current date) - 45 * days
    set d2 to (current date) + 21 * days
    tell application "Calendar"
        repeat with wanted in argv
            repeat with c in (calendars whose name is (wanted as text))
                set gotSums to summary of (every event of c whose start date ≥ d1 and start date ≤ d2)
                set gotStarts to start date of (every event of c whose start date ≥ d1 and start date ≤ d2)
                repeat with i from 1 to (count of gotSums)
                    set out to out & "" & FS & my txt(item i of gotSums) & FS ¬
                        & my stamp(item i of gotStarts) & FS & "" & FS & "" & FS & (wanted as text) & RS
                end repeat
            end repeat
        end repeat
    end tell
"""
    + _TAIL,
    # ---------------------------------------------------------------- Notes
    "notes.list": _HEAD
    + """
    tell application "Notes"
        set gotNames to name of folders
        repeat with i from 1 to (count of gotNames)
            set out to out & (item i of gotNames as text) & FS & ((count of notes of folder i) as text) & RS
        end repeat
    end tell
"""
    + _TAIL,
    "notes.read": _HEAD
    + """
    tell application "Notes"
        repeat with wanted in argv
            repeat with f in (folders whose name is (wanted as text))
                set gotIds to id of (notes of f whose password protected is false)
                set gotNames to name of (notes of f whose password protected is false)
                set gotDates to modification date of (notes of f whose password protected is false)
                set gotBodies to plaintext of (notes of f whose password protected is false)
                repeat with i from 1 to (count of gotIds)
                    set out to out & my txt(item i of gotIds) & FS & my txt(item i of gotNames) & FS ¬
                        & my stamp(item i of gotDates) & FS & my txt(item i of gotBodies) & FS ¬
                        & (wanted as text) & RS
                end repeat
            end repeat
        end repeat
    end tell
"""
    + _TAIL,
    # ---------------------------------------------------------------- Reminders
    "reminders.list": _HEAD
    + """
    tell application "Reminders"
        set gotNames to name of lists
        repeat with i from 1 to (count of gotNames)
            set out to out & (item i of gotNames as text) & FS & ((count of reminders of list i) as text) & RS
        end repeat
    end tell
"""
    + _TAIL,
    "reminders.read": _HEAD
    + """
    tell application "Reminders"
        repeat with wanted in argv
            repeat with l in (lists whose name is (wanted as text))
                set gotIds to id of reminders of l
                set gotNames to name of reminders of l
                set gotDones to completed of reminders of l
                set gotDues to due date of reminders of l
                set gotBodies to body of reminders of l
                repeat with i from 1 to (count of gotIds)
                    set out to out & my txt(item i of gotIds) & FS & my txt(item i of gotNames) & FS ¬
                        & ((item i of gotDones) as text) & FS & my stamp(item i of gotDues) & FS ¬
                        & my txt(item i of gotBodies) & FS & (wanted as text) & RS
                end repeat
            end repeat
        end repeat
    end tell
"""
    + _TAIL,
    # ---------------------------------------------------------------- Mail
    # Names only: counting the messages of every mailbox of every account is slow.
    "mail.list": _HEAD
    + """
    tell application "Mail"
        repeat with acc in accounts
            set gotNames to name of mailboxes of acc
            repeat with n in gotNames
                set out to out & my txt(name of acc) & " / " & (n as text) & FS & "" & RS
            end repeat
        end repeat
    end tell
"""
    + _TAIL,
    # Only the newest messages of a chosen mailbox, and whole lists per request instead of
    # one request per message. Mail hands over what it has on this Mac.
    "mail.read": _HEAD
    + """
    tell application "Mail"
        repeat with wanted in argv
            repeat with acc in accounts
                repeat with mb in mailboxes of acc
                    if (my txt(name of acc) & " / " & my txt(name of mb)) is (wanted as text) then
                        set total to count of messages of mb
                        if total > 25 then set total to 25
                        if total > 0 then
                            set gotIds to message id of (messages 1 thru total of mb)
                            set gotSums to subject of (messages 1 thru total of mb)
                            set gotDates to date received of (messages 1 thru total of mb)
                            set gotNames to sender of (messages 1 thru total of mb)
                            set gotBodies to content of (messages 1 thru total of mb)
                            repeat with i from 1 to total
                                set out to out & my txt(item i of gotIds) & FS & my txt(item i of gotSums) ¬
                                    & FS & my stamp(item i of gotDates) & FS & my txt(item i of gotNames) ¬
                                    & FS & my txt(item i of gotBodies) & FS & (wanted as text) & RS
                            end repeat
                        end if
                    end if
                end repeat
            end repeat
        end repeat
    end tell
"""
    + _TAIL,
}


_RUNNING: set[subprocess.Popen[str]] = set()
_LOCK = threading.Lock()


def stop_running() -> None:
    """Stop every script that is still running (on revoke, on end of session, on exit)."""
    with _LOCK:
        running = list(_RUNNING)
    for process in running:
        process.kill()


atexit.register(stop_running)


def osascript(script: str, args: list[str], timeout: float) -> str:
    """Run one of the read-only scripts above. Errors come back as codes, never as text
    from the app (an error message can contain content). A script that runs out of time is
    stopped, so it cannot keep the app busy behind our back."""
    process = subprocess.Popen(
        ["/usr/bin/osascript", "-e", script, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    with _LOCK:
        _RUNNING.add(process)
    try:
        out, err = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise DeskThreadError(ErrorCode.READ_FAILED, "the app did not answer in time") from None
    finally:
        with _LOCK:
            _RUNNING.discard(process)
    if process.returncode != 0:
        if process.returncode < 0:  # stopped by us: the source was switched off
            raise DeskThreadError(ErrorCode.READ_CANCELLED)
        refused = any(code in err for code in ("-1743", "-1744", "-10004"))
        raise DeskThreadError(ErrorCode.OS_PERMISSION_MISSING if refused else ErrorCode.READ_FAILED)
    return out


def _records(raw: str) -> list[list[str]]:
    return [r.strip("\n").split(FS) for r in raw.split(RS) if r.strip("\n")]


def _when(stamp: str) -> datetime | None:
    try:
        return datetime.fromisoformat(stamp).replace(tzinfo=UTC) if stamp else None
    except ValueError:
        return None


class MacAppAdapter:
    """One Mac app as a source. Read-only; reads only with a grant from the broker."""

    def __init__(
        self, name: str, kind: SourceKind, label: str, app_path: str, runner: Runner = osascript
    ) -> None:
        self._name, self._kind, self._label = name, kind, label
        self._app_path, self._run = Path(app_path), runner
        self._permission = OsPermission.UNKNOWN

    @property
    def source_id(self) -> str:
        return f"mac:{self._name}"

    @property
    def kind(self) -> SourceKind:
        return self._kind

    @property
    def label(self) -> str:
        return self._label

    def installed(self) -> bool:
        return self._app_path.exists()

    def os_permission(self) -> OsPermission:
        return self._permission

    def cancel(self) -> None:
        """The source was switched off: stop a read that is still running."""
        stop_running()

    def _call(self, script: str, args: list[str], timeout: float) -> list[list[str]]:
        try:
            raw = self._run(SCRIPTS[f"{self._name}.{script}"], args, timeout)
        except DeskThreadError as err:
            if err.code is ErrorCode.OS_PERMISSION_MISSING:
                self._permission = OsPermission.MISSING
            raise
        self._permission = OsPermission.GRANTED
        return _records(raw)

    def list_scopes(self) -> list[Scope]:
        """Names and counts only. The first call makes macOS ask the user for the app."""
        seen: dict[str, int | None] = {}
        for record in self._call("list", [], 60):
            count = int(record[1]) if len(record) > 1 and record[1].isdigit() else None
            name = record[0]
            seen[name] = (seen[name] or 0) + count if name in seen and count is not None else count
        return [Scope(scope_id=n, label=n, item_count=c) for n, c in sorted(seen.items())]

    def read(self, grant: ReadGrant) -> Iterator[Item | Uncounted]:
        if grant.source_id != self.source_id:
            raise DeskThreadError(ErrorCode.SOURCE_NOT_ALLOWED)
        grant.raise_if_cancelled()
        records = self._call("read", sorted(grant.scope_ids), 240)
        timed = self._name in ("mail", "calendar") and (
            getattr(grant, "days", None) or getattr(grant, "since", None)
        )
        start, end = period.window(grant, 30, 365)
        for record in records:
            grant.raise_if_cancelled()  # a revoke stops the read between two items
            item = PARSERS[self._name](self.source_id, record)
            if item is None:
                continue
            if timed and item.date and not start <= item.date <= end:
                continue  # outside the period the user chose
            yield item


def _event(source_id: str, r: list[str]) -> Item | None:
    if len(r) < 6:
        return None
    uid, title, start, end, who, calendar = r[:6]
    begins = _when(start)
    people = ", ".join(p.strip() for p in who.split(",") if p.strip())
    when = begins.strftime("%a %d %b %Y %H:%M") if begins else "no date"
    lines = [f"{title or '(no title)'} - {when}", *([f"With: {people}"] if people else [])]
    return Item(
        source_id=source_id,
        item_id=item_id("e", source_id, uid or f"{title}{start}"),
        kind=ItemKind.EVENT,
        title=title or "(no title)",
        units=to_units(lines),
        date=begins,
        location=f"Calendar: {calendar}",
        meta={"attendees": people, "end": end},
    )


def _note(source_id: str, r: list[str]) -> Item | None:
    if len(r) < 5:
        return None
    uid, title, modified, text, folder = r[:5]
    units = to_units(text.splitlines())
    if not units:
        return None
    # The date is the one the writer wrote in the note. The app's own "modified" time is
    # kept beside it but is not treated as when the note was written.
    head = "\n".join(u.text for u in units[:3])
    return Item(
        source_id=source_id,
        item_id=item_id("n", source_id, uid or title),
        kind=ItemKind.NOTE,
        title=title or units[0].text,
        units=units,
        date=find_date(head, now().year),
        location=f"Notes: {folder}",
        meta={"modified": modified},
    )


def _reminder(source_id: str, r: list[str]) -> Item | None:
    if len(r) < 6:
        return None
    uid, title, completed, due, body, name = r[:6]
    done = completed.strip().lower() == "true"
    lines = [f"{title} [{'done' if done else 'open'}]", *body.splitlines()]
    return Item(
        source_id=source_id,
        item_id=item_id("r", source_id, uid or title),
        kind=ItemKind.REMINDER,
        title=title,
        units=to_units(lines),
        date=_when(due) or find_date(title, now().year),
        location=f"Reminders: {name}",
        meta={"status": "done" if done else "open", "list": name},
    )


def _mail(source_id: str, r: list[str]) -> Item | None:
    if len(r) < 6:
        return None
    uid, subject, received, sender, text, mailbox = r[:6]
    return Item(
        source_id=source_id,
        item_id=item_id("m", source_id, uid or f"{subject}{received}"),
        kind=ItemKind.MAIL,
        title=subject or "(no subject)",
        units=to_units([f"Subject: {subject}", *text.splitlines()]),
        date=_when(received),
        location=f"Mail: {mailbox}",
        meta={"from": sender},
    )


PARSERS: dict[str, Callable[[str, list[str]], Item | None]] = {
    "calendar": _event,
    "notes": _note,
    "reminders": _reminder,
    "mail": _mail,
}


def mac_apps(runner: Runner = osascript) -> list[SourceAdapter]:
    """The Mac apps DeskThread can read, if they are on this Mac. Nothing is read here."""
    from app.sources.mac_calendar import CalendarAdapter

    known = (
        ("mail", SourceKind.MAIL, "Mail"),
        ("notes", SourceKind.NOTES, "Notes"),
        ("reminders", SourceKind.REMINDERS, "Reminders"),
    )
    apps: list[Any] = [CalendarAdapter(runner)]
    apps += [
        MacAppAdapter(name, kind, label, f"/System/Applications/{label}.app", runner)
        for name, kind, label in known
    ]
    return [app for app in apps if app.installed()]
