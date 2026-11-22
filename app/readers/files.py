"""Readers for files, one function per type (FT-04 to FT-07). Read-only, binary mode.

read_file() is the single entry: it returns the Items of a file, or raises UNSUPPORTED_TYPE
or READ_FAILED. The caller has already passed the access policy (G1).
"""

import csv
import email
import email.policy
import io
import re
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from pypdf import PdfReader

from app.readers.common import find_date, item_id, to_units
from contracts.errors import DeskThreadError, ErrorCode
from contracts.items import Item, ItemKind

IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg"})
MAX_BYTES = 5_000_000  # a note-sized limit; larger files are counted as unsupported

Reader = Callable[[bytes, str, str, str, int], list[Item]]


def _text(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _note(data: bytes, source_id: str, key: str, name: str, year: int) -> list[Item]:
    lines = _text(data).splitlines()
    units = to_units(lines)
    title = units[0].text.lstrip("# ").strip() if units else name
    # Only the top of a note says when it was written; a date further down is content.
    head = "\n".join(u.text for u in units[:3])
    return [
        Item(
            source_id=source_id,
            item_id=item_id("n", source_id, key),
            kind=ItemKind.NOTE,
            title=title,
            units=units,
            date=find_date(head, year),
            location=key,
        )
    ]


def _document(data: bytes, source_id: str, key: str, name: str, year: int) -> list[Item]:
    item = _note(data, source_id, key, name, year)[0]
    return [
        item.model_copy(update={"kind": ItemKind.DOCUMENT, "item_id": item_id("d", source_id, key)})
    ]


def _chat(data: bytes, source_id: str, key: str, name: str, year: int) -> list[Item]:
    item = _note(data, source_id, key, name, year)[0]
    return [
        item.model_copy(update={"kind": ItemKind.CHAT, "item_id": item_id("c", source_id, key)})
    ]


class _TextOnly(HTMLParser):
    """HTML mail to plain text. Tags are dropped, scripts and styles too; nothing is fetched."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._skip += 1
        elif tag in {"p", "br", "div", "h1", "h2", "h3", "li", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._skip:
            self._skip -= 1
        elif tag in {"p", "div", "h1", "h2", "h3", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    parser = _TextOnly()
    parser.feed(html)
    return "".join(parser.parts)


def _mail(data: bytes, source_id: str, key: str, name: str, year: int) -> list[Item]:
    msg = email.message_from_bytes(data, policy=email.policy.default)
    body = msg.get_body(preferencelist=("plain", "html"))
    text = ""
    if body is not None:
        text = str(body.get_content())
        if body.get_content_subtype() == "html":
            text = html_to_text(text)
    subject = str(msg.get("Subject", name))
    sender = str(msg.get("From", ""))
    sent = msg.get("Date")
    date = sent.datetime if sent is not None and hasattr(sent, "datetime") else None
    if date is not None and date.tzinfo is None:
        date = date.replace(tzinfo=UTC)
    units = to_units([f"Subject: {subject}", *text.splitlines()])
    return [
        Item(
            source_id=source_id,
            item_id=item_id("m", source_id, key),
            kind=ItemKind.MAIL,
            title=subject,
            units=units,
            date=date,
            location=key,
            meta={"from": sender, "to": str(msg.get("To", ""))},
        )
    ]


def _unfold(text: str) -> list[str]:
    return re.sub(r"\r?\n[ \t]", "", text).splitlines()


def _ics_time(value: str, params: str) -> datetime | None:
    match = re.fullmatch(r"(\d{8})(?:T(\d{6}))?(Z)?", value.strip())
    if not match:
        return None
    stamp = datetime.strptime(match[1] + (match[2] or "000000"), "%Y%m%d%H%M%S")
    tz = re.search(r"TZID=([^;:]+)", params)
    if match[3]:
        return stamp.replace(tzinfo=UTC)
    try:
        return stamp.replace(tzinfo=ZoneInfo(tz[1]) if tz else UTC)
    except (KeyError, ValueError):
        return stamp.replace(tzinfo=UTC)


def _calendar(data: bytes, source_id: str, key: str, name: str, year: int) -> list[Item]:
    items: list[Item] = []
    event: dict[str, str] | None = None
    people: list[str] = []
    for line in _unfold(_text(data)):
        if line == "BEGIN:VEVENT":
            event, people = {}, []
        elif line == "END:VEVENT" and event is not None:
            start = _ics_time(event.get("DTSTART", ""), event.get("DTSTART;", ""))
            title = event.get("SUMMARY", "(no title)")
            when = start.strftime("%a %d %b %Y %H:%M") if start else "no date"
            lines = [f"{title} - {when}"]
            if people:
                lines.append("With: " + ", ".join(people))
            minutes = re.fullmatch(r"PT(\d+)M", event.get("DURATION", ""))
            end = start + timedelta(minutes=int(minutes[1])) if start and minutes else None
            items.append(
                Item(
                    source_id=source_id,
                    item_id=item_id("e", source_id, f"{key}#{event.get('UID', len(items))}"),
                    kind=ItemKind.EVENT,
                    title=title,
                    units=to_units(lines),
                    date=start,
                    location=key,
                    meta={
                        "attendees": ", ".join(people),
                        "end": end.isoformat() if end else "",
                    },
                )
            )
            event = None
        elif event is not None and ":" in line:
            head, value = line.split(":", 1)
            prop, _, params = head.partition(";")
            if prop == "ATTENDEE":
                cn = re.search(r"CN=([^;:]+)", params)
                people.append(cn[1] if cn else value.removeprefix("mailto:"))
            else:
                event[prop] = value
                event[prop + ";"] = params
    return items


_REMINDER = re.compile(r"^\[( |x|X)\]\s*(.+)$")


def _reminders(data: bytes, source_id: str, key: str, name: str, year: int) -> list[Item]:
    """A plain-text reminders list: a list name, then "[ ] open" and "[x] done" lines."""
    items: list[Item] = []
    list_name = name
    for number, line in enumerate(_text(data).splitlines(), 1):
        match = _REMINDER.match(line.strip())
        if not match:
            if line.strip():
                list_name = line.strip()
            continue
        done = match[1].lower() == "x"
        text = match[2].strip()
        items.append(
            Item(
                source_id=source_id,
                item_id=item_id("r", source_id, f"{key}#{number}"),
                kind=ItemKind.REMINDER,
                title=text,
                units=to_units([f"{text} [{'done' if done else 'open'}]"]),
                date=find_date(text, year),
                location=key,
                meta={"status": "done" if done else "open", "list": list_name},
            )
        )
    return items


def _csv(data: bytes, source_id: str, key: str, name: str, year: int) -> list[Item]:
    rows = list(csv.reader(io.StringIO(_text(data))))
    if not rows:
        return _document(b"", source_id, key, name, year)
    header, body = rows[0], rows[1:]
    # Each row becomes one unit that carries its column names, so a quote explains itself.
    lines = [", ".join(f"{h}: {v}" for h, v in zip(header, row, strict=False) if v) for row in body]
    return [
        Item(
            source_id=source_id,
            item_id=item_id("d", source_id, key),
            kind=ItemKind.DOCUMENT,
            title=name,
            units=to_units(lines),
            location=key,
        )
    ]


def _docx(data: bytes, source_id: str, key: str, name: str, year: int) -> list[Item]:
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        xml = zf.read("word/document.xml")
    if b"<!DOCTYPE" in xml or b"<!ENTITY" in xml:
        raise DeskThreadError(ErrorCode.READ_FAILED)  # no entity tricks in a Word file
    root = ElementTree.fromstring(xml)  # noqa: S314
    lines = ["".join(t.text or "" for t in p.iter(f"{ns}t")) for p in root.iter(f"{ns}p")]
    units = to_units(lines)
    return [
        Item(
            source_id=source_id,
            item_id=item_id("d", source_id, key),
            kind=ItemKind.DOCUMENT,
            title=units[0].text if units else name,
            units=units,
            location=key,
        )
    ]


def _pdf(data: bytes, source_id: str, key: str, name: str, year: int) -> list[Item]:
    reader = PdfReader(io.BytesIO(data))
    lines: list[str] = []
    for page in reader.pages:
        lines += page.extract_text().splitlines()
    units = to_units(lines)
    return [
        Item(
            source_id=source_id,
            item_id=item_id("d", source_id, key),
            kind=ItemKind.DOCUMENT,
            title=units[0].text if units else name,
            units=units,
            location=key,
        )
    ]


def _image(data: bytes, source_id: str, key: str, name: str, year: int) -> list[Item]:
    """An image has no units until the local model reads it, in memory (FT-39)."""
    return [
        Item(
            source_id=source_id,
            item_id=item_id("i", source_id, key),
            kind=ItemKind.IMAGE,
            title=name,
            units=(),
            location=key,
            meta={"reading": "pending"},
        )
    ]


READERS: dict[str, Reader] = {
    ".md": _note,
    ".txt": _note,
    ".eml": _mail,
    ".ics": _calendar,
    ".csv": _csv,
    ".docx": _docx,
    ".pdf": _pdf,
    ".vtt": _chat,
    **dict.fromkeys(IMAGE_SUFFIXES, _image),
}

# How a file is read also depends on which source it belongs to.
BY_ROLE: dict[str, Reader] = {"reminders": _reminders, "chat": _chat, "document": _document}


def supported(path: Path) -> bool:
    return path.suffix.lower() in READERS


# Kinds whose date is the file's own changed-time (user, 2026-11-22). A mail, a calendar
# entry and a reminder carry their own date and keep it.
_DATED_BY_FILE = frozenset({ItemKind.NOTE, ItemKind.DOCUMENT, ItemKind.IMAGE, ItemKind.CHAT})


def _file_dated(item: Item, path: Path) -> Item:
    """A note, document or picture is dated by its file: when the file was last written.
    A date written at the top of the text is kept beside it, as "written"."""
    if item.kind not in _DATED_BY_FILE:
        return item
    meta = {**item.meta, **({"written": item.date.date().isoformat()} if item.date else {})}
    changed = datetime.fromtimestamp(path.stat().st_mtime).astimezone()
    return item.model_copy(update={"date": changed, "meta": meta})


def read_file(path: Path, source_id: str, key: str, year: int, role: str = "") -> list[Item]:
    """Read one file that already passed the access policy."""
    suffix = path.suffix.lower()
    reader = READERS.get(suffix)
    if reader is None:
        raise DeskThreadError(ErrorCode.UNSUPPORTED_TYPE)
    if suffix in {".md", ".txt"} and role in BY_ROLE:
        reader = BY_ROLE[role]
    try:
        with path.open("rb") as handle:  # read-only, binary (R2)
            data = handle.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise DeskThreadError(ErrorCode.UNSUPPORTED_TYPE)
        return [_file_dated(item, path) for item in reader(data, source_id, key, path.name, year)]
    except DeskThreadError:
        raise
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        raise DeskThreadError(ErrorCode.READ_FAILED) from exc
    except Exception as exc:
        raise DeskThreadError(ErrorCode.READ_FAILED) from exc
