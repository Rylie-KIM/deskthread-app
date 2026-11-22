"""Prepare my next meeting (FT-34): the next one-to-ones, from allowed calendars only."""

import re
from datetime import timedelta

from app.clock import now
from contracts.api import Meeting
from contracts.items import Item, ItemKind

ONE_TO_ONE = re.compile(r"^\s*(?:1:1|1-1|one[- ]to[- ]one)\s+(?:with\s+)?([A-Z][\w-]+)", re.I)


def upcoming(items: list[Item], days: int = 7) -> list[Meeting]:
    """Events from now on with exactly one other person, soonest first."""
    start, end = now(), now() + timedelta(days=days)
    found = []
    for item in items:
        people = [p.strip() for p in item.meta.get("attendees", "").split(",") if p.strip()]
        named = ONE_TO_ONE.match(item.title)
        if not people and named:
            people = [named[1]]
        in_window = item.date is not None and start <= item.date <= end
        if item.kind is ItemKind.EVENT and item.date and in_window and len(people) == 1:
            found.append(
                Meeting(
                    meeting_id=item.item_id, title=item.title, start=item.date, person=people[0]
                )
            )
    return sorted(found, key=lambda m: m.start)
