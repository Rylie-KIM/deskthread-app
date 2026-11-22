"""Shared helpers for the readers: ids, units and dates."""

import hashlib
import re
from datetime import UTC, datetime

from contracts.items import Unit

MONTHS = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1
    )
}
_MONTH = "|".join(MONTHS)
# "Fri 6 Nov 2026", "14 Oct 2026", "28 Oct", "Wednesday 4 November 2026"
_DAY_MONTH = re.compile(rf"\b(\d{{1,2}})\s+({_MONTH})[a-z]*\.?(?:\s+(\d{{4}}))?\b", re.I)
# "23/10", "02/11/2026"
_SLASHED = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\b")
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


def item_id(prefix: str, source_id: str, key: str) -> str:
    """Short, stable for a session and unique across sources. Says nothing about content."""
    digest = hashlib.sha256(f"{source_id}\n{key}".encode()).hexdigest()[:10]
    return f"{prefix}-{digest}"


def to_units(lines: list[str]) -> tuple[Unit, ...]:
    """One unit per non-empty line, numbered from 1. The text is kept as written."""
    kept = [line.strip() for line in lines if line.strip()]
    return tuple(Unit(number=i, text=text) for i, text in enumerate(kept, 1))


def find_date(text: str, default_year: int) -> datetime | None:
    """The first date the writer gave in this text, or None. File times are never used."""
    found: list[tuple[int, datetime]] = []
    for match in _ISO.finditer(text):
        found.append((match.start(), _make(int(match[1]), int(match[2]), int(match[3]))))
    for match in _DAY_MONTH.finditer(text):
        year = int(match[3]) if match[3] else default_year
        found.append((match.start(), _make(year, MONTHS[match[2].lower()[:3]], int(match[1]))))
    for match in _SLASHED.finditer(text):
        year = int(match[3]) if match[3] else default_year
        found.append((match.start(), _make(year, int(match[2]), int(match[1]))))  # day/month
    dated = sorted((pos, d) for pos, d in found if d is not None)
    return dated[0][1] if dated else None


def _make(year: int, month: int, day: int) -> datetime:
    try:
        return datetime(year, month, day, tzinfo=UTC)
    except ValueError:
        return None  # type: ignore[return-value]  # "14/21" is not a date; filtered above
