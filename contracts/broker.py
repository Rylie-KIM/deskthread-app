"""Permission broker interface (FT-53, FT-15, R15).

The single gate every source passes. Every source starts Off. One call grants, one call
revokes, and a revoke takes effect at once: items of that source leave memory and reads in
progress are cancelled.
"""

from datetime import date as Day  # noqa: N812 (a field is called `date`)
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from contracts.adapters import OsPermission, ReadGrant, Scope
from contracts.items import SourceKind


class SourceStatus(StrEnum):
    OFF = "off"
    ON = "on"  # read permission for this session; there is no other kind of permission


class PermissionRequest(BaseModel):
    """What the request card shows before the user clicks Allow."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    label: str
    what_will_be_read: str  # plain words
    scopes: tuple[Scope, ...]
    os_permission: OsPermission


class SourceState(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_id: str
    kind: SourceKind
    label: str
    status: SourceStatus
    os_permission: OsPermission
    allowed_scope_ids: tuple[str, ...] = ()
    items_in_memory: int = 0
    # Why this source cannot be switched on right now, in plain words; "" when it can. Today:
    # pictures with an AI model that cannot read pictures. (contract 1.17)
    blocked: str = ""


class AuditAction(StrEnum):
    GRANT = "grant"
    REVOKE = "revoke"
    REVOKE_ALL = "revoke_all"
    DENIED = "denied"
    READ = "read"
    FOLDER_ADDED = "folder_added"  # the user chose a folder (contract 1.16)
    FOLDER_REMOVED = "folder_removed"


class AuditLine(BaseModel):
    """In memory only. Ids and counts, never content (FT-44)."""

    model_config = ConfigDict(frozen=True)

    at: datetime
    action: AuditAction
    source_id: str
    count: int = 0


@runtime_checkable
class PermissionBroker(Protocol):
    def states(self) -> list[SourceState]: ...

    def request(self, source_id: str) -> PermissionRequest: ...

    def grant(
        self,
        source_id: str,
        scope_ids: frozenset[str],
        days: int | None = None,
        since: Day | None = None,
        until: Day | None = None,
    ) -> SourceState:
        """Allow reading for this session. Reading is the only permission there is."""
        ...

    def revoke(self, source_id: str) -> SourceState:
        """Immediate: cancel reads in progress and drop the source's items from memory."""
        ...

    def revoke_all(self) -> list[SourceState]: ...

    def is_allowed(self, source_id: str) -> bool: ...

    def read_grant(self, source_id: str) -> ReadGrant:
        """Raises SOURCE_NOT_ALLOWED unless the source is On."""
        ...

    def audit(self) -> list[AuditLine]: ...
