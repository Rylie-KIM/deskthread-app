"""Image reading (FT-39): the local model reads pictures and screenshots, in memory only.

A reading is the model's transcription of an image. It is kept in this object, keyed by a
hash of the image bytes, so an image is read once per session; Forget now clears it.
A quote from an image proves it matches the model's reading, not the pixels: the viewer
says so, and shows the image beside the reading.
"""

import hashlib
from pathlib import Path

from app import prompts
from app.model import Model
from app.policy import AccessPolicy
from app.store import SessionStore
from contracts.errors import DeskThreadError
from contracts.items import ItemKind, Unit


class ImageReader:
    def __init__(self, policy: AccessPolicy, store: SessionStore, model: Model) -> None:
        self._policy, self._store, self._model = policy, store, model
        self._readings: dict[str, tuple[str, ...]] = {}

    @property
    def held(self) -> int:
        return len(self._readings)

    def forget(self) -> None:
        self._readings.clear()

    def read_pending(self) -> int:
        """Read allowed images that have no reading yet. Returns how many could not be read."""
        failed = 0
        for item in self._store.items():
            if item.kind is not ItemKind.IMAGE or item.meta.get("reading") != "pending":
                continue
            try:
                real = self._policy.check_read(Path(item.meta["path"]))  # G1 again, on the path
                with real.open("rb") as handle:
                    data = handle.read()
                key = hashlib.sha256(data).hexdigest()
                if key not in self._readings:
                    text = self._model.complete(prompts.READ_IMAGE, images=[data]).strip()
                    lines = [] if text.upper().strip(". ") == "NONE" else text.splitlines()
                    self._readings[key] = tuple(line.strip() for line in lines if line.strip())
                lines_read = self._readings[key]
            except (DeskThreadError, OSError, KeyError):
                failed += 1
                continue
            units = tuple(Unit(number=n, text=t) for n, t in enumerate(lines_read, 1))
            meta = {**item.meta, "reading": "done" if units else "no text found"}
            self._store.replace(
                item.model_copy(update={"units": units, "meta": meta, "read_by_model": True})
            )
        return failed
