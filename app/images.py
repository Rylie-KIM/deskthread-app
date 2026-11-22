"""Image reading (FT-39): the local model reads pictures and screenshots, in memory only.

A reading is the model's transcription of an image. It is kept in this object, keyed by a
hash of the image bytes, so an image is read once per session; Forget now clears it.
A quote from an image proves it matches the model's reading, not the pixels: the viewer
says so, and shows the image beside the reading.
"""

import hashlib
from collections.abc import Callable
from pathlib import Path

from app import prompts
from app.model import Model
from app.policy import AccessPolicy
from app.store import SessionStore
from contracts.errors import DeskThreadError
from contracts.items import Item, ItemKind, Unit


class ImageReader:
    def __init__(self, policy: AccessPolicy, store: SessionStore, model: Model) -> None:
        self._policy, self._store, self._model = policy, store, model
        self._readings: dict[str, tuple[str, ...] | None] = {}  # None: the AI failed on it

    @property
    def held(self) -> int:
        return len(self._readings)

    def forget(self) -> None:
        self._readings.clear()

    def read_pending(self, progress: Callable[[int, int], None] | None = None) -> int:
        """Read allowed pictures that have no reading yet. Returns how many could not be read.

        A picture read earlier in this session is not read again: its reading is kept by
        the hash of its bytes until Clear memory or End session. A picture the AI failed on
        is not tried again either. `progress(n, total)` is called before each new reading.
        """
        pending = [
            i
            for i in self._store.items()
            if i.kind is ItemKind.IMAGE and i.meta.get("reading") == "pending"
        ]
        if not getattr(self._model, "reads_pictures", True):
            return len(pending)  # the chosen model cannot read pictures: unread, and counted
        failed = 0
        found: list[tuple[Item, str, bytes]] = []
        for item in pending:
            try:
                real = self._policy.check_read(Path(item.meta["path"]))  # G1 again, on the path
                with real.open("rb") as handle:
                    data = handle.read()
            except (DeskThreadError, OSError, KeyError):
                failed += 1
                continue
            found.append((item, hashlib.sha256(data).hexdigest(), data))
        new = len({key for _, key, _ in found if key not in self._readings})
        done = 0
        for item, key, data in found:
            if key not in self._readings:
                done += 1
                if progress:
                    progress(done, new)  # also where a stopped question ends
                try:
                    text = self._model.complete(prompts.READ_IMAGE, images=[data]).strip()
                except DeskThreadError:
                    self._readings[key] = None  # remembered, so it is not tried again
                else:
                    lines = [] if text.upper().strip(". ") == "NONE" else text.splitlines()
                    self._readings[key] = tuple(line.strip() for line in lines if line.strip())
            lines_read = self._readings[key]
            if lines_read is None:
                failed += 1
                continue
            units = tuple(Unit(number=n, text=t) for n, t in enumerate(lines_read, 1))
            meta = {**item.meta, "reading": "done" if units else "no text found"}
            self._store.replace(
                item.model_copy(update={"units": units, "meta": meta, "read_by_model": True})
            )
        return failed
