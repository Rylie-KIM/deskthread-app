"""The one item shape every source adapter returns.

A note, a mail, an event, a reminder, a chat export, a document and an image all become an
Item made of numbered units. The model cites (item_id, unit number); code extracts the quote
from the unit, so a quote is verbatim by construction (G4).
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceKind(StrEnum):
    NOTES = "notes"
    CALENDAR = "calendar"
    MAIL = "mail"
    REMINDERS = "reminders"
    CHAT_EXPORT = "chat_export"
    DOCUMENTS = "documents"
    IMAGES = "images"


class ItemKind(StrEnum):
    NOTE = "note"
    EVENT = "event"
    MAIL = "mail"
    REMINDER = "reminder"
    CHAT = "chat"
    DOCUMENT = "document"
    IMAGE = "image"


class Unit(BaseModel):
    """One citable piece of an item: a line, a sentence or a fragment."""

    model_config = ConfigDict(frozen=True)

    number: int = Field(ge=1)
    text: str = Field(min_length=1)


class Item(BaseModel):
    """One thing read from a source. Held in memory only; never written to disk."""

    model_config = ConfigDict(frozen=True)

    source_id: str = Field(min_length=1)
    item_id: str = Field(min_length=1)  # stable within a session, unique across sources
    kind: ItemKind
    title: str
    units: tuple[Unit, ...]
    # When the item is from: a mail's header date, an event's start, a reminder's due date;
    # for a note, document or picture file the file's own changed-time; for a note in the
    # Notes app the time the app says it was last changed (user, 2026-11-22). None means
    # "undated".
    date: datetime | None = None
    # Where the item lives, for the viewer: a path for files, an app label otherwise.
    location: str = ""
    # Small facts a reader extracted: "status" (open/done), "attendees", "from", "due" ...
    meta: dict[str, str] = Field(default_factory=dict)
    # True when the text is a model's reading of an image and may contain errors (FT-39).
    read_by_model: bool = False

    @model_validator(mode="after")
    def _units_numbered_from_one(self) -> "Item":
        numbers = [u.number for u in self.units]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError("units must be numbered 1..n without gaps")
        return self

    @property
    def undated(self) -> bool:
        return self.date is None

    def unit(self, number: int) -> Unit | None:
        """The unit with this number, or None when it is out of range."""
        if 1 <= number <= len(self.units):
            return self.units[number - 1]
        return None


class Uncounted(BaseModel):
    """A file a reader could not read. It is counted in coverage, never skipped silently."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    location: str
    reason: str  # an ErrorCode value
