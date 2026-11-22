"""Picture reading (FT-39): the text of a picture or screenshot, in memory only.

macOS's own text recognition (app/ocr.py) reads it first: fast, on this Mac, and with any
answering AI. Only where it finds no text is the answering AI asked to read the picture, and
only if that AI can. A reading is kept in this object, keyed by a hash of the picture's bytes,
so a picture is read once per session; Clear memory and End session drop it. Nothing is
written. A quote from a picture proves it matches the reading, not the pixels: the viewer
says so and shows the picture beside the reading.
"""

import hashlib
from collections.abc import Callable
from pathlib import Path

from app import ocr, prompts
from app.model import Model
from app.policy import AccessPolicy
from app.store import SessionStore
from contracts.errors import DeskThreadError
from contracts.items import Item, ItemKind, Unit

OCR_NAME = "macOS text recognition"
AI_NAME = "the AI on this Mac"


class ImageReader:
    def __init__(
        self,
        policy: AccessPolicy,
        store: SessionStore,
        model: Model,
        recognise: Callable[[bytes], list[str] | None] | None = None,
    ) -> None:
        self._policy, self._store, self._model = policy, store, model
        self._recognise = recognise or ocr.recognise
        self._readings: dict[str, tuple[str, ...] | None] = {}  # None: the AI failed on it
        self._by: dict[str, str] = {}  # key -> who read it
        self._empty: set[str] = set()  # macOS read the picture and found no text

    @property
    def held(self) -> int:
        return len(self._readings) + len(self._empty)

    def forget(self) -> None:
        self._readings.clear()
        self._by.clear()
        self._empty.clear()

    def _can_use_model(self) -> bool:
        return bool(getattr(self._model, "reads_pictures", True))

    def read_pending(
        self,
        progress: Callable[[int, int], None] | None = None,
        check: Callable[[], None] | None = None,
        use_model: bool = True,
    ) -> int:
        """Read allowed pictures that have no reading yet. Returns how many could not be read.

        macOS reads each one first. With `use_model`, a picture without any text is then read
        by the answering AI if it can; without it (when a source is switched on) such a picture
        stays pending for the first question. `progress(n, total)` is called before each new
        reading and is where a stopped question ends; `check` is called when an AI reading
        was cut off.
        """
        pending = [
            i
            for i in self._store.items()
            if i.kind is ItemKind.IMAGE and i.meta.get("reading") == "pending"
        ]
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
        unique = {key: data for _, key, data in found}
        todo = [k for k in unique if k not in self._readings and k not in self._empty]
        total = len(todo)
        for done, key in enumerate(todo, 1):  # the first look: macOS text recognition
            if progress:
                progress(done, total)
            lines = self._recognise(unique[key])
            if lines:
                self._readings[key], self._by[key] = tuple(lines), OCR_NAME
            elif lines is not None:
                self._empty.add(key)
        if use_model and self._can_use_model():
            second = [k for k in unique if k not in self._readings]
            for number, key in enumerate(second, 1):  # the second look: the answering AI
                if progress:
                    progress(number, len(second))
                try:
                    text = self._model.complete(prompts.READ_IMAGE, images=[unique[key]]).strip()
                except DeskThreadError:
                    if check:
                        check()  # cut off by Stop: not a failure of this picture
                    self._readings[key] = None  # remembered, so it is not tried again
                else:
                    lines2 = [] if text.upper().strip(". ") == "NONE" else text.splitlines()
                    self._readings[key] = tuple(x.strip() for x in lines2 if x.strip())
                    self._by[key] = AI_NAME
        final = use_model or not self._can_use_model()
        for item, key, _data in found:
            if key in self._readings:
                lines_read = self._readings[key]
                if lines_read is None:
                    failed += 1
                    continue
            elif key in self._empty and final:
                lines_read = ()  # macOS found no text and nothing else will look
            elif key in self._empty:
                continue  # stays pending: the first question may ask the AI
            else:
                failed += 1  # macOS could not read it and the AI is not asked
                continue
            units = tuple(Unit(number=n, text=t) for n, t in enumerate(lines_read, 1))
            meta = {
                **item.meta,
                "reading": "done" if units else "no text found",
                "read_with": self._by.get(key, OCR_NAME),
            }
            self._store.replace(
                item.model_copy(update={"units": units, "meta": meta, "read_by_model": True})
            )
        return failed
