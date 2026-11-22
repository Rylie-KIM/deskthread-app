"""The Memory panel and Forget now (FT-35, FT-37).

Between questions the items of allowed sources stay in the backend's memory, and the model
runtime keeps the model (and its last prompt) loaded. Forget now clears both and the app
stays open. It cannot prove that the bytes were erased: freed memory belongs to the
operating system. The panel shows numbers a user can compare with Activity Monitor.
"""

import os

from fastapi import FastAPI

from app.proof.processes import watched
from app.runtime import Runtime
from contracts.api import MemoryState
from contracts.broker import SourceStatus


def state(runtime: Runtime) -> MemoryState:
    by_source: dict[str, int] = {}
    readings = 0
    if runtime.session is not None:
        for source in runtime.session.broker.states():
            if source.status is SourceStatus.ON and source.items_in_memory:
                by_source[source.label] = source.items_in_memory
        readings = runtime.session.assistant.readings_held
    return MemoryState(
        items_held=sum(by_source.values()),
        items_by_source=by_source,
        image_readings_held=readings,
        model_loaded=runtime.gateway.loaded() if runtime.gateway else False,
        processes=tuple(watched(runtime.server.pid if runtime.server else None)),
        mac_memory_mb=round(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 1048576),
    )


def forget(runtime: Runtime) -> MemoryState:
    """Drop every item and image reading, and unload the model. Access choices stay."""
    if runtime.session is not None:
        runtime.session.assistant.forget()
    if runtime.gateway is not None:
        runtime.gateway.unload()
    return state(runtime)


def register(app: FastAPI, runtime: Runtime) -> None:
    @app.get("/api/memory")
    def memory() -> MemoryState:
        return state(runtime)

    @app.post("/api/forget")
    def forget_now() -> MemoryState:
        with runtime.ask_lock:  # never in the middle of an answer
            return forget(runtime)
