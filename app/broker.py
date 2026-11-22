"""The permission broker (FT-53, FT-15): the single gate every source passes.

Every source starts Off. grant() turns one on for this session; revoke() turns it off at
once: reads in progress are cancelled and whoever holds items of that source is told to
drop them. Nothing is remembered between sessions, because nothing is saved (R4).
"""

import threading
from collections.abc import Callable

from app.clock import now
from contracts.adapters import ReadGrant, SourceAdapter
from contracts.broker import (
    AuditAction,
    AuditLine,
    PermissionRequest,
    SourceState,
    SourceStatus,
)
from contracts.errors import DeskThreadError, ErrorCode
from contracts.items import SourceKind

WHAT_IS_READ: dict[SourceKind, str] = {
    SourceKind.NOTES: "The text of the notes in the folders you tick. Nothing is changed.",
    SourceKind.CALENDAR: "Titles, times and attendees of events in the calendars you tick.",
    SourceKind.MAIL: "Sender, date, subject and text of messages in the mailbox you tick. "
    "Mail is shown as plain text; pictures in a mail are never fetched.",
    SourceKind.REMINDERS: "Reminders in the lists you tick: title, due date, done or open.",
    SourceKind.CHAT_EXPORT: "Chat text files in the folders you tick.",
    SourceKind.DOCUMENTS: "Documents (.docx, .pdf, .csv, .txt, .md) in the folders you tick.",
    SourceKind.IMAGES: "Pictures and screenshots in the folders you tick. The model on this "
    "laptop reads their text, in memory only.",
}


class Grant:
    """Proof that a read is allowed right now. Cancelled the moment access is revoked."""

    def __init__(self, source_id: str, scope_ids: frozenset[str]) -> None:
        self._source_id, self._scope_ids = source_id, scope_ids
        self._cancel = threading.Event()

    @property
    def source_id(self) -> str:
        return self._source_id

    @property
    def scope_ids(self) -> frozenset[str]:
        return self._scope_ids

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def cancel(self) -> None:
        self._cancel.set()

    def raise_if_cancelled(self) -> None:
        if self._cancel.is_set():
            raise DeskThreadError(ErrorCode.READ_CANCELLED)


class Broker:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._adapters: dict[str, SourceAdapter] = {}
        self._grants: dict[str, Grant] = {}
        self._audit: list[AuditLine] = []
        self._on_revoke: list[Callable[[str], None]] = []
        self._count: Callable[[str], int] = lambda _source_id: 0

    # ----------------------------------------------------------------- wiring
    def register(self, adapter: SourceAdapter) -> None:
        with self._lock:
            self._adapters[adapter.source_id] = adapter  # a new source always starts Off

    def unregister_all(self) -> None:
        self.revoke_all()
        with self._lock:
            self._adapters.clear()

    def replace(self, prefix: str, adapters: list[SourceAdapter]) -> None:
        """Swap every source whose id starts with the prefix: revoke them, then register
        the new ones. Used when the user chooses another folder; other sources keep their state."""
        with self._lock:
            old = [s for s in self._adapters if s.startswith(prefix)]
        for source_id in old:
            self.revoke(source_id, quiet=True)
        with self._lock:
            for source_id in old:
                del self._adapters[source_id]
            for adapter in adapters:
                self._adapters[adapter.source_id] = adapter

    def on_revoke(self, callback: Callable[[str], None]) -> None:
        self._on_revoke.append(callback)

    def count_with(self, counter: Callable[[str], int]) -> None:
        self._count = counter

    def adapter(self, source_id: str) -> SourceAdapter:
        try:
            return self._adapters[source_id]
        except KeyError:
            raise DeskThreadError(ErrorCode.SOURCE_UNKNOWN) from None

    def _note(self, action: AuditAction, source_id: str, count: int = 0) -> None:
        self._audit.append(AuditLine(at=now(), action=action, source_id=source_id, count=count))

    def note_read(self, source_id: str, count: int) -> None:
        with self._lock:
            self._note(AuditAction.READ, source_id, count)

    # ----------------------------------------------------------------- the contract
    def _state(self, source_id: str) -> SourceState:
        adapter = self.adapter(source_id)
        grant = self._grants.get(source_id)
        status = SourceStatus.ON if grant else SourceStatus.OFF
        return SourceState(
            source_id=source_id,
            kind=adapter.kind,
            label=adapter.label,
            status=status,
            os_permission=adapter.os_permission(),
            allowed_scope_ids=tuple(sorted(grant.scope_ids)) if grant else (),
            items_in_memory=self._count(source_id) if grant else 0,
        )

    def states(self) -> list[SourceState]:
        with self._lock:
            return [self._state(s) for s in self._adapters]

    def request(self, source_id: str) -> PermissionRequest:
        adapter = self.adapter(source_id)
        return PermissionRequest(
            source_id=source_id,
            label=adapter.label,
            what_will_be_read=WHAT_IS_READ[adapter.kind],
            scopes=tuple(adapter.list_scopes()),
            os_permission=adapter.os_permission(),
        )

    def grant(self, source_id: str, scope_ids: frozenset[str]) -> SourceState:
        adapter = self.adapter(source_id)
        known = {s.scope_id for s in adapter.list_scopes()}
        chosen = (scope_ids & known) if scope_ids else known
        if not chosen:
            raise DeskThreadError(ErrorCode.BAD_REQUEST)
        self.revoke(source_id, quiet=True)  # a new choice of scopes replaces the old one
        with self._lock:
            self._grants[source_id] = Grant(source_id, frozenset(chosen))
            self._note(AuditAction.GRANT, source_id, len(chosen))
            return self._state(source_id)

    def revoke(self, source_id: str, quiet: bool = False) -> SourceState:
        self.adapter(source_id)
        with self._lock:
            grant = self._grants.pop(source_id, None)
            if grant:
                grant.cancel()  # stops a read in progress at its next step
        dropped = self._count(source_id) if grant else 0
        if grant:
            for callback in self._on_revoke:
                callback(source_id)  # items of this source leave memory now
        with self._lock:
            if grant and not quiet:
                self._note(AuditAction.REVOKE, source_id, dropped)
            return self._state(source_id)

    def revoke_all(self) -> list[SourceState]:
        with self._lock:
            active = list(self._grants)
        for source_id in active:
            self.revoke(source_id, quiet=True)
        with self._lock:
            if active:
                self._note(AuditAction.REVOKE_ALL, "*", len(active))
            return [self._state(s) for s in self._adapters]

    def is_allowed(self, source_id: str) -> bool:
        with self._lock:
            return source_id in self._grants

    def read_grant(self, source_id: str) -> ReadGrant:
        with self._lock:
            grant = self._grants.get(source_id)
        if grant is None:
            raise DeskThreadError(ErrorCode.SOURCE_NOT_ALLOWED)
        return grant

    def audit(self) -> list[AuditLine]:
        with self._lock:
            return list(self._audit)
