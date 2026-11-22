"""Calendar through the Mac's own calendar framework (EventKit), read only.

The Calendar app's scripting interface takes about a second per event, so a calendar with a
hundred events took minutes and timed out. EventKit answers in milliseconds. Only fetch
calls are used here: nothing is created, changed or removed, and a test scans this file for
the calls that would. macOS asks the user once for calendar access; if that is refused or
the framework is missing, the slower scripting route in mac.py is used instead.
"""

import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from app.readers.common import item_id, to_units
from app.sources.mac import MacAppAdapter, Runner, osascript
from contracts.adapters import OsPermission, ReadGrant, Scope
from contracts.errors import DeskThreadError, ErrorCode
from contracts.items import Item, ItemKind, SourceKind, Uncounted

DAYS_BACK, DAYS_AHEAD = 45, 21
ASK_SECONDS = 90  # how long to wait for the user to answer macOS's question


def _framework() -> Any:
    try:
        import EventKit
    except ImportError:
        return None
    return EventKit


class CalendarAdapter:
    """The Calendar source. Uses EventKit when allowed, else the scripting route."""

    source_id = "mac:calendar"
    kind = SourceKind.CALENDAR
    label = "Calendar"

    def __init__(self, runner: Runner = osascript, framework: Any = None) -> None:
        self._kit = framework if framework is not None else _framework()
        self._store: Any = None
        self._script = MacAppAdapter(
            "calendar", SourceKind.CALENDAR, "Calendar", "/System/Applications/Calendar.app", runner
        )
        self._permission = OsPermission.UNKNOWN

    def installed(self) -> bool:
        return self._script.installed()

    def os_permission(self) -> OsPermission:
        return self._permission if self._store is not None else self._script.os_permission()

    def cancel(self) -> None:
        self._script.cancel()

    def _open(self) -> bool:
        """Ask macOS for calendar access once. True when EventKit may be used."""
        if self._store is not None:
            return True
        if self._kit is None:
            return False
        store = self._kit.EKEventStore.alloc().init()
        answered = threading.Event()
        granted: list[bool] = []

        def answer(ok: bool, _error: Any) -> None:
            granted.append(bool(ok))
            answered.set()

        try:
            store.requestFullAccessToEventsWithCompletion_(answer)
        except AttributeError:  # an older macOS
            store.requestAccessToEntityType_completion_(self._kit.EKEntityTypeEvent, answer)
        answered.wait(ASK_SECONDS)
        if granted and granted[0]:
            self._store, self._permission = store, OsPermission.GRANTED
            return True
        return False

    def _calendars(self) -> list[Any]:
        return list(self._store.calendarsForEntityType_(self._kit.EKEntityTypeEvent) or [])

    def list_scopes(self) -> list[Scope]:
        if not self._open():
            return self._script.list_scopes()
        names = sorted({str(c.title()) for c in self._calendars()})
        return [Scope(scope_id=name, label=name, item_count=None) for name in names]

    def read(self, grant: ReadGrant) -> Iterator[Item | Uncounted]:
        if grant.source_id != self.source_id:
            raise DeskThreadError(ErrorCode.SOURCE_NOT_ALLOWED)
        if not self._open():
            yield from self._script.read(grant)
            return
        grant.raise_if_cancelled()
        from Foundation import NSDate

        wanted = [c for c in self._calendars() if str(c.title()) in grant.scope_ids]
        if not wanted:
            return
        window = self._store.predicateForEventsWithStartDate_endDate_calendars_(
            NSDate.dateWithTimeIntervalSinceNow_(-DAYS_BACK * 86400),
            NSDate.dateWithTimeIntervalSinceNow_(DAYS_AHEAD * 86400),
            wanted,
        )
        for event in self._store.eventsMatchingPredicate_(window) or []:
            grant.raise_if_cancelled()
            yield _item(self.source_id, event)


def _moment(value: Any) -> datetime | None:
    return datetime.fromtimestamp(value.timeIntervalSince1970(), UTC) if value is not None else None


def _item(source_id: str, event: Any) -> Item:
    title = str(event.title() or "(no title)")
    start, end = _moment(event.startDate()), _moment(event.endDate())
    people = ", ".join(
        str(p.name()) for p in (event.attendees() or []) if p.name() and not p.isCurrentUser()
    )
    when = start.astimezone().strftime("%a %d %b %Y %H:%M") if start else "no date"
    lines = [f"{title} - {when}", *([f"With: {people}"] if people else [])]
    return Item(
        source_id=source_id,
        item_id=item_id("e", source_id, f"{event.eventIdentifier()}{start}"),
        kind=ItemKind.EVENT,
        title=title,
        units=to_units(lines),
        date=start,
        location=f"Calendar: {event.calendar().title()}",
        meta={"attendees": people, "end": end.isoformat() if end else ""},
    )
