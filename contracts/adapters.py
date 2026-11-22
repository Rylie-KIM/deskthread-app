"""Source adapter interface.

An adapter reads one kind of source (a folder of files, the Notes app, ...), read-only.
It never decides whether it may read: it is handed a ReadGrant by the permission broker
and must stop as soon as the grant is cancelled (R15).
"""

from collections.abc import Iterator
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

from contracts.items import Item, SourceKind, Uncounted


class OsPermission(StrEnum):
    """The operating system's own permission for an app, a second layer above ours."""

    NOT_NEEDED = "not_needed"  # plain files chosen by the user
    GRANTED = "granted"
    MISSING = "missing"
    UNKNOWN = "unknown"  # not asked yet


class Scope(BaseModel):
    """A part of a source the user can allow: a folder, a calendar, a list, a mailbox."""

    model_config = ConfigDict(frozen=True)

    scope_id: str
    label: str
    item_count: int | None = None  # names and counts only; no content is read to list scopes


@runtime_checkable
class ReadGrant(Protocol):
    """Proof that the broker allows a read right now. Adapters check it between items."""

    @property
    def source_id(self) -> str: ...

    @property
    def scope_ids(self) -> frozenset[str]: ...

    @property
    def cancelled(self) -> bool: ...

    def raise_if_cancelled(self) -> None:
        """Raise DeskThreadError(READ_CANCELLED) when the grant was revoked."""
        ...


@runtime_checkable
class SourceAdapter(Protocol):
    @property
    def source_id(self) -> str: ...

    @property
    def kind(self) -> SourceKind: ...

    @property
    def label(self) -> str: ...

    def os_permission(self) -> OsPermission: ...

    def list_scopes(self) -> list[Scope]:
        """Names and counts only. Must not read content."""
        ...

    def read(self, grant: ReadGrant) -> Iterator[Item | Uncounted]:
        """Yield items of the granted scopes. Read calls only; stops when cancelled."""
        ...
