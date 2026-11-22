"""What the session holds in memory, and nothing else (R4): the items of allowed sources.

Items live in this object only. They are dropped when a source is revoked, on Forget now
and when the session ends. Nothing here is ever written to disk.
"""

import threading

from app.broker import Broker
from contracts.errors import DeskThreadError, ErrorCode
from contracts.items import Item, Uncounted


class SessionStore:
    def __init__(self, broker: Broker) -> None:
        self._broker = broker
        self._lock = threading.RLock()
        self._items: dict[str, list[Item]] = {}
        self._uncounted: dict[str, list[Uncounted]] = {}
        broker.on_revoke(self.drop)
        broker.count_with(self.count)

    def load(self, source_id: str) -> int:
        """Read one allowed source through the broker. Returns how many items are held."""
        grant = self._broker.read_grant(source_id)  # raises unless the source is On
        adapter = self._broker.adapter(source_id)
        items: list[Item] = []
        uncounted: list[Uncounted] = []
        try:
            for thing in adapter.read(grant):
                grant.raise_if_cancelled()
                if isinstance(thing, Item):
                    items.append(thing)
                else:
                    uncounted.append(thing)
        except DeskThreadError as err:
            if err.code is ErrorCode.READ_CANCELLED:
                return 0
            raise
        with self._lock:
            if grant.cancelled:  # revoked while reading: keep nothing
                return 0
            self._items[source_id], self._uncounted[source_id] = items, uncounted
        self._broker.note_read(source_id, len(items))
        return len(items)

    def refresh(self) -> None:
        """Read every allowed source again, so a file deleted meanwhile is gone (U10)."""
        for state in self._broker.states():
            if self._broker.is_allowed(state.source_id):
                self.load(state.source_id)

    def drop(self, source_id: str) -> None:
        with self._lock:
            self._items.pop(source_id, None)
            self._uncounted.pop(source_id, None)

    def forget(self) -> None:
        with self._lock:
            self._items.clear()
            self._uncounted.clear()

    def replace(self, item: Item) -> None:
        """Swap in a newer version of an item (an image once the model has read it)."""
        with self._lock:
            held = self._items.get(item.source_id, [])
            for index, old in enumerate(held):
                if old.item_id == item.item_id:
                    held[index] = item

    def count(self, source_id: str) -> int:
        with self._lock:
            return len(self._items.get(source_id, []))

    def items(self) -> list[Item]:
        """Items of sources that are allowed right now. The broker is asked again here."""
        with self._lock:
            return [
                item
                for source_id, held in self._items.items()
                if self._broker.is_allowed(source_id)
                for item in held
            ]

    def uncounted(self) -> list[Uncounted]:
        with self._lock:
            return [
                u
                for source_id, held in self._uncounted.items()
                if self._broker.is_allowed(source_id)
                for u in held
            ]

    def get(self, item_id: str) -> Item | None:
        return next((i for i in self.items() if i.item_id == item_id), None)
