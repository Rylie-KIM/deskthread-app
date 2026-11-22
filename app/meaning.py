"""Search by meaning (the user's request of 2026-11-22: related notes must be found even
when they use other words, or do not name the person).

A small local model turns a text into a list of numbers; two texts that say similar things
get similar lists. The numbers are made on this Mac, held in memory for the session only,
and dropped on Clear memory and End session. If the search model is not on this Mac, this
part is simply off and search works by words as before.
"""

import hashlib
import math
from typing import Any

from contracts.errors import DeskThreadError
from contracts.items import Item

Vector = tuple[float, ...]
MAX_CHARS = 1400  # enough to say what a note is about; long notes are cut here
BATCH = 24


def text_of(item: Item) -> str:
    return (item.title + "\n" + "\n".join(u.text for u in item.units))[:MAX_CHARS]


def _unit(values: list[float]) -> Vector:
    length = math.sqrt(sum(v * v for v in values)) or 1.0
    return tuple(v / length for v in values)


def likeness(a: Vector, b: Vector) -> float:
    """How alike two texts are, from about 0 (unrelated) to 1 (the same)."""
    return sum(x * y for x, y in zip(a, b, strict=False))


class Meaning:
    def __init__(self, model: Any) -> None:
        self._model = model
        self._held: dict[str, Vector] = {}  # by the hash of the text, never by its content

    def forget(self) -> None:
        self._held.clear()

    @property
    def held(self) -> int:
        return len(self._held)

    def _make(self, texts: list[str]) -> list[Vector] | None:
        embed = getattr(self._model, "embed", None)
        if embed is None:
            return None
        try:
            made = embed(texts)
        except DeskThreadError:
            return None
        if made is None or len(made) != len(texts):
            return None
        return [_unit([float(v) for v in values]) for values in made]

    def of_text(self, text: str) -> Vector | None:
        made = self._make([text[:MAX_CHARS]])
        return made[0] if made else None

    def of_items(self, items: list[Item]) -> dict[str, Vector] | None:
        """item id -> vector, for items that have text. None when meaning search is off."""
        keys = {
            item.item_id: hashlib.sha256(text_of(item).encode()).hexdigest()
            for item in items
            if item.units
        }
        texts = {keys[item.item_id]: text_of(item) for item in items if item.units}
        missing = [key for key in texts if key not in self._held]
        for start in range(0, len(missing), BATCH):
            part = missing[start : start + BATCH]
            made = self._make([texts[key] for key in part])
            if made is None:
                return None
            self._held.update(zip(part, made, strict=True))
        return {item_id: self._held[key] for item_id, key in keys.items()}
