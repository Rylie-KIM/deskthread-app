"""Coming up (FT-34): the next calendar entries, from allowed calendars only."""

import re
from datetime import timedelta

from app.clock import now
from contracts.api import Meeting
from contracts.items import Item, ItemKind

ONE_TO_ONE = re.compile(r"^\s*(?:1:1|1-1|one[- ]to[- ]one)\s+(?:with\s+)?([A-Z][\w-]+)", re.I)


def upcoming(items: list[Item], days: int = 7, limit: int = 6) -> list[Meeting]:
    """The next calendar entries, soonest first. An entry with exactly one other person
    carries that person's name; any other entry carries none."""
    start, end = now(), now() + timedelta(days=days)
    found = []
    for item in items:
        if item.kind is not ItemKind.EVENT or item.date is None or not start <= item.date <= end:
            continue
        people = [p.strip() for p in item.meta.get("attendees", "").split(",") if p.strip()]
        named = ONE_TO_ONE.match(item.title)
        if not people and named:
            people = [named[1]]
        person = people[0] if len(people) == 1 else ""
        found.append(
            Meeting(meeting_id=item.item_id, title=item.title, start=item.date, person=person)
        )
    return sorted(found, key=lambda m: m.start)[:limit]
