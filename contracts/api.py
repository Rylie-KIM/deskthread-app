"""HTTP API shapes (the UI and the backend agree on these and nothing else).

All routes live under /api on 127.0.0.1 and need the session token header (FT-23).
ROUTES is the frozen list; the OpenAPI document is generated from these models.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from contracts.broker import AuditLine, PermissionRequest, SourceState
from contracts.gates import GateResult

TOKEN_HEADER = "X-DeskThread-Token"

ROUTES: dict[str, str] = {
    "GET /api/session": "SessionInfo",
    "GET /api/sources": "list[SourceState]",
    "GET /api/folders": "list[FolderInfo]",  # the folders in use (contract 1.6)
    "POST /api/folder": "list[SourceState]",  # adds a folder; body: FolderChoice
    "POST /api/folder/remove": "list[SourceState]",  # body: FolderChoice
    "GET /api/sources/{source_id}/request": "PermissionRequest",
    "POST /api/sources/{source_id}/grant": "SourceState",  # body: GrantBody
    "POST /api/sources/{source_id}/revoke": "SourceState",
    "POST /api/sources/revoke-all": "list[SourceState]",
    "GET /api/meetings": "list[Meeting]",
    "POST /api/prepare": "Answer",  # body: PrepareBody
    "POST /api/ask": "Answer",  # body: AskBody
    "GET /api/progress": "Progress",  # which step a running question is on
    "GET /api/items/{item_id}": "ItemView",
    "GET /api/items/{item_id}/image": "bytes",
    "GET /api/models": "list[ModelInfo]",
    "POST /api/models/select": "list[ModelInfo]",  # body: ModelPick
    "POST /api/models/download": "list[ModelInfo]",  # body: ModelPick; runs in the background
    "GET /api/memory": "MemoryState",
    "POST /api/forget": "MemoryState",
    "GET /api/proof": "Proof",
    "POST /api/end-session": "Receipt",
}


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class SessionInfo(_Frozen):
    app: str = "DeskThread"
    contract_version: str
    model_tag: str
    model_digest: str
    prompt_version: str
    now: datetime  # the session clock (fixable for tests and the recording)
    # Path of the invented demo laptop when it has been built, so the first screen can offer
    # "try it with the demo". Empty when there is none. (contract 1.1)
    demo_folder: str = ""


class ModelInfo(_Frozen):
    """One model the user may choose (contract 1.3)."""

    tag: str
    name: str
    maker: str
    download_gb: float
    reads_pictures: bool
    good_for: str
    installed: bool
    selected: bool
    tested: bool  # run through DeskThread's own tests and pinned to that exact version
    downloading: int | None = None  # percent, while a download runs
    failed: bool = False


class ModelPick(_Frozen):
    tag: str


class FolderChoice(_Frozen):
    path: str = ""


class FolderInfo(_Frozen):
    path: str
    name: str


class GrantBody(_Frozen):
    scope_ids: tuple[str, ...] = ()  # empty = every scope the request listed


class Meeting(_Frozen):
    meeting_id: str
    title: str
    start: datetime
    person: str  # the one other attendee, used as a search word; empty for other entries


class PrepareBody(_Frozen):
    meeting_id: str


class AskBody(_Frozen):
    question: str = Field(min_length=1, max_length=500)


class Progress(_Frozen):
    """The step a running question is on, in plain words. Empty when nothing is running."""

    step: str = ""
    number: int = 0
    of: int = 0


class PointStatus(StrEnum):
    DONE = "done"
    OPEN = "open"
    CHANGED = "changed"
    SUPERSEDED = "superseded"


class Citation(_Frozen):
    item_id: str
    unit: int
    quote: str  # extracted by code from the unit, never written by the model
    source_id: str
    source_label: str
    title: str
    date: datetime | None
    undated: bool
    read_by_model: bool = False


class BriefPoint(_Frozen):
    label: str
    status: PointStatus
    citations: tuple[Citation, ...]
    note: str = ""  # e.g. "a newer note changed this"


class Coverage(_Frozen):
    """accessible = searched + unsupported; cited is a subset of given_to_model (U9)."""

    accessible: int
    searched: int
    unsupported: int
    given_to_model: int
    cited: int
    by_source: dict[str, int]  # accessible items per allowed source
    not_accessible: dict[str, int | None]  # Off and Locked sources: counts only, or unknown


class AnswerKind(StrEnum):
    BRIEF = "brief"
    NOT_FOUND = "not_found"
    NO_SOURCES = "no_sources"


class Answer(_Frozen):
    kind: AnswerKind
    question: str
    points: tuple[BriefPoint, ...]
    message: str  # plain words, e.g. "I could not find this in the notes you shared."
    coverage: Coverage
    gate_trace: tuple[GateResult, ...]
    given_item_ids: tuple[str, ...]
    seconds: float
    # True when the question is about things promised or to do: only then does a status
    # (done, still to do, ...) mean anything, and only then is it shown. (contract 1.5)
    show_status: bool = False


class UnitView(_Frozen):
    number: int
    text: str


class ItemView(_Frozen):
    """Read-only viewer data for one item (FT-14). Text is shown as text, never as HTML."""

    item_id: str
    source_label: str
    kind: str
    title: str
    date: datetime | None
    location: str
    units: tuple[UnitView, ...]
    read_by_model: bool
    has_image: bool


class ProcessInfo(_Frozen):
    name: str
    pid: int
    memory_mb: float


class MemoryState(_Frozen):
    items_held: int
    items_by_source: dict[str, int]
    image_readings_held: int
    model_loaded: bool
    processes: tuple[ProcessInfo, ...]


class Connection(_Frozen):
    process: str
    pid: int
    remote: str  # address:port
    local_only: bool


class FolderHash(_Frozen):
    label: str
    files: int
    before: str
    now: str
    unchanged: bool


class Proof(_Frozen):
    sampled_at: datetime
    connections: tuple[Connection, ...]  # open connections, sampled; not a full history
    all_local: bool
    folders: tuple[FolderHash, ...]
    files_written_by_app: int  # always 0: the app writes nothing (R4)
    telemetry_off: dict[str, bool]
    audit: tuple[AuditLine, ...]
    limits: str


class Receipt(_Frozen):
    """Shown on End session. Counts and hashes only, never note text (FT-40)."""

    items_read: int
    items_given_to_model: int
    questions: int
    memory_cleared: bool
    model_unloaded: bool
    files_written_by_app: int
    all_connections_local: bool
    folders: tuple[FolderHash, ...]
    limits: str


class ApiError(_Frozen):
    code: str
    message: str


__all__ = [
    "ROUTES",
    "TOKEN_HEADER",
    "Answer",
    "AnswerKind",
    "ApiError",
    "AskBody",
    "BriefPoint",
    "Citation",
    "Connection",
    "Coverage",
    "FolderChoice",
    "FolderHash",
    "FolderInfo",
    "GrantBody",
    "ItemView",
    "Meeting",
    "MemoryState",
    "ModelInfo",
    "ModelPick",
    "PermissionRequest",
    "PointStatus",
    "PrepareBody",
    "ProcessInfo",
    "Progress",
    "Proof",
    "Receipt",
    "SessionInfo",
    "SourceState",
    "UnitView",
]
