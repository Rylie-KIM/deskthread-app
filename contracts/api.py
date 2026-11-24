"""HTTP API shapes (the UI and the backend agree on these and nothing else).

All routes live under /api on 127.0.0.1 and need the session token header (FT-23).
ROUTES is the frozen list; the OpenAPI document is generated from these models.
"""

from datetime import date as Day  # noqa: N812 (a field is called `date`)
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
    "GET /api/sources/{source_id}/icon": "bytes",  # the app's own icon, as the Mac shows it
    "POST /api/sources/{source_id}/revoke": "SourceState",
    "POST /api/sources/revoke-all": "list[SourceState]",
    "GET /api/meetings": "list[Meeting]",
    "POST /api/prepare": "Answer",  # body: PrepareBody
    "POST /api/ask": "Answer",  # body: AskBody
    "GET /api/people": "list[Spellings]",  # other ways the user writes a name (1.15)
    "POST /api/people": "list[Spellings]",  # body: list[Spellings]; replaces the list
    "GET /api/progress": "Progress",  # which step a running question is on
    "GET /api/preparing": "Preparing",  # the pictures being read after a switch is turned on
    "POST /api/cancel": "Progress",  # stop the running question (contract 1.8)
    "GET /api/items/{item_id}": "ItemView",
    "GET /api/items/{item_id}/image": "bytes",
    "POST /api/items/{item_id}/reveal": "ItemView",  # select the file in Finder, or open its app
    "GET /api/models": "list[ModelInfo]",
    "POST /api/models/select": "list[ModelInfo]",  # body: ModelPick
    "POST /api/models/download": "list[ModelInfo]",  # body: ModelPick; runs in the background
    "GET /api/memory": "MemoryState",
    "POST /api/forget": "MemoryState",
    "GET /api/proof": "Proof",
    "GET /api/proof/connections": "ConnectionCheck",  # the Mac's own listing, run now
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
    # "answers": a model that reads and answers. "search": the small model for search by
    # meaning; it is used automatically once it is on this Mac. (contract 1.14)
    role: str = "answers"
    parameters: str = ""  # how many parameters it has, e.g. "7.5B (computes like 4B)" (1.18)


class Spellings(_Frozen):
    """One person and the other ways the user writes the name. Held in memory for the
    session; like the access settings it survives Clear memory and ends with the session."""

    name: str = Field(min_length=1, max_length=60)
    also: tuple[str, ...] = Field(default=(), max_length=8)


class ModelPick(_Frozen):
    tag: str


class FolderChoice(_Frozen):
    path: str = ""


class FolderInfo(_Frozen):
    path: str
    name: str
    # What is in the folder, by file name only (contract 1.8). Videos and unknown formats
    # cannot be read; they are counted so the user sees that they were not taken in.
    files: int = 0
    pictures: int = 0
    videos: int = 0
    other: int = 0


class GrantBody(_Frozen):
    scope_ids: tuple[str, ...] = ()  # empty = every scope the request listed
    # How many days back to read, for sources where time matters (Calendar, Mail).
    # None: the source's own default. (contract 1.7)
    days: int | None = Field(default=None, ge=1, le=366)
    # Or an exact range, both days included (contract 1.9). It wins over `days`.
    since: Day | None = None
    until: Day | None = None


class Meeting(_Frozen):
    meeting_id: str
    title: str
    start: datetime
    person: str  # the one other attendee, used as a search word; empty for other entries


class PrepareBody(_Frozen):
    meeting_id: str


class AskBody(_Frozen):
    question: str = Field(min_length=1, max_length=500)


class PictureStage(_Frozen):
    """One of the two stages of reading pictures (contract 1.21)."""

    # waiting, running, done, not_needed (nothing for this stage to do), or skipped (the AI
    # model in use cannot read pictures)
    state: str = "waiting"
    done: int = 0
    total: int = 0


class PictureRead(_Frozen):
    """A picture whose text was read, for the "See the text" list (contract 1.21)."""

    item_id: str
    title: str
    source_label: str
    date: datetime | None
    read_with: str  # "macOS text recognition" or "the AI on this Mac"


class Preparing(_Frozen):
    """Work done after a source is switched on and before the first question: reading the text
    of pictures. While `active`, a question would have to wait (contract 1.20)."""

    active: bool = False
    done: int = 0
    total: int = 0
    what: str = ""  # "Reading pictures", or "Looking at pictures without text"
    # Contract 1.21: the two stages on their own, a number that grows with each finished job,
    # and, once a job is over, what it read.
    text: PictureStage = PictureStage()  # stage 1: macOS text recognition
    look: PictureStage = PictureStage()  # stage 2: the AI looks at pictures without text
    job: int = 0
    by_macos: int = 0
    by_ai: int = 0
    no_text: int = 0
    pictures: tuple[PictureRead, ...] = ()


class Progress(_Frozen):
    """The step a running question is on, in plain words. Empty when nothing is running."""

    step: str = ""
    number: int = 0
    of: int = 0
    detail: str = ""  # for a long step, how far it is: "picture 3 of 13" (contract 1.8)


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
    # Set when the person asked about is NOT named in the quoted notes: the point is only
    # possibly related, and is shown apart. "meaning" (it reads like the notes that do name
    # the person) or "time" (written around a meeting with the person); `why` says it in
    # plain words. (contract 1.14)
    related: str = ""
    why: str = ""
    # Words of the question that occur in the quoted lines: why these lines (contract 1.9).
    matched: tuple[str, ...] = ()


class Coverage(_Frozen):
    """accessible = searched + unsupported; cited is a subset of given_to_model (U9)."""

    accessible: int
    searched: int
    unsupported: int
    given_to_model: int
    cited: int
    by_source: dict[str, int]  # accessible items per allowed source
    not_accessible: dict[str, int | None]  # Off and Locked sources: counts only, or unknown


class ItemRef(_Frozen):
    """An item named by what a person recognises: its title, where it is from, its date."""

    item_id: str
    title: str
    source_label: str
    kind: str
    date: datetime | None = None


class RelatedRef(_Frozen):
    item: ItemRef
    how: str  # why it looked related, in plain words


class DroppedQuote(_Frozen):
    item: ItemRef
    quote: str  # the line, copied from the note
    why: str  # why the check dropped it


class Unread(_Frozen):
    location: str  # where the file is, inside its folder
    why: str


class AnswerKind(StrEnum):
    BRIEF = "brief"
    NOT_FOUND = "not_found"
    NO_SOURCES = "no_sources"
    STOPPED = "stopped"  # the user stopped the question (contract 1.8)


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
    # Up to two sentences by the AI, each resting on quoted lines; a sentence that does not
    # is dropped by code. The quotes stay the proof. (contract 1.9)
    summary: tuple[str, ...] = ()
    # The AI model that answered, by its plain name, and what was left out on the way, as
    # counts: "off_limits", "unreadable", "dropped" (real quotes on another subject),
    # "nowhere" (citations of lines that do not exist), "instructions" (notes holding
    # orders to an assistant). Only what is above zero is listed. (contract 1.13)
    model_name: str = ""
    left_out: dict[str, int] = Field(default_factory=dict)
    # The items behind each stage of "how this was checked" (contract 1.19): everything read,
    # what looked related (and how), the quotes the check dropped, what could not be read,
    # the names of files kept out of reach, the notes that held instructions.
    read_items: tuple[ItemRef, ...] = ()
    related_items: tuple[RelatedRef, ...] = ()
    dropped_quotes: tuple[DroppedQuote, ...] = ()
    unread: tuple[Unread, ...] = ()
    off_limits_names: tuple[str, ...] = ()
    instruction_notes: tuple[ItemRef, ...] = ()


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
    # Where the original lives: "file" (can be shown in Finder), "app" (its Mac app can be
    # opened) or "" (contract 1.11). DeskThread never opens or changes the original itself.
    origin: str = ""


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
    mac_memory_mb: float = 0  # all the memory this Mac has, to compare against (contract 1.8)
    # Memory other programs could still take right now, as macOS counts it: free, inactive,
    # speculative and purgeable pages. Measured each time, like the total. (contract 1.12)
    mac_free_mb: float = 0


class Connection(_Frozen):
    process: str
    pid: int
    remote: str  # address:port
    local_only: bool


class FileChange(_Frozen):
    """One file that is different from when its folder was chosen. Name and times only: no
    file is opened to find this out. macOS does not record which program changed a file,
    so only the owning user account can be named. (contract 1.9)"""

    name: str  # path inside the folder
    what: str  # "added" | "changed" | "removed"
    when: datetime | None = None  # the file's own changed-time; None for a removed file
    owner: str = ""  # the user account that owns the file


class FolderHash(_Frozen):
    label: str
    files: int
    before: str
    now: str
    unchanged: bool
    changes: tuple[FileChange, ...] = ()  # the newest ones, at most 25 (contract 1.9)
    changes_total: int = 0


class ConnectionCheck(_Frozen):
    """The Mac's own tool `lsof`, run now on DeskThread's programs: the command as a person
    could type it, what macOS printed, and the same lines read for them. (contract 1.10)"""

    command: str
    output: str
    connections: tuple[Connection, ...]
    all_local: bool
    ran_at: datetime


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
    """Shown on End session. Counts, hashes and the names of changed files only, never note
    text (FT-40)."""

    items_read: int
    items_given_to_model: int
    questions: int
    memory_cleared: bool
    model_unloaded: bool
    files_written_by_app: int
    all_connections_local: bool
    folders: tuple[FolderHash, ...]
    limits: str
    # Per source, by its label: how many items were read, and shown to the AI (contract 1.9).
    read_by_source: dict[str, int] = Field(default_factory=dict)
    given_by_source: dict[str, int] = Field(default_factory=dict)


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
