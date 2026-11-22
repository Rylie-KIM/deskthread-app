"""Choosing the AI model (T-47): a short list of approved models; one is in use.

A model that is not on this Mac yet is downloaded when the user asks. The download is done
by the model server and is the only time it uses the internet. Nothing about the user's
notes is part of it.
"""

import threading

from fastapi import FastAPI

from app import config
from app.runtime import Runtime
from contracts.api import ModelInfo, ModelPick
from contracts.errors import DeskThreadError, ErrorCode


class Downloads:
    """Progress of downloads in this session, in memory."""

    def __init__(self) -> None:
        self.percent: dict[str, int] = {}
        self.failed: set[str] = set()
        self._lock = threading.Lock()

    def start(self, runtime: Runtime, tag: str) -> None:
        gateway = runtime.gateway
        if gateway is None:
            raise DeskThreadError(ErrorCode.MODEL_UNAVAILABLE)
        with self._lock:
            if tag in self.percent:
                return  # already running
            self.percent[tag] = 0
            self.failed.discard(tag)

        def work() -> None:
            try:
                gateway.pull(tag, lambda p: self.percent.__setitem__(tag, p))
            except DeskThreadError:
                self.failed.add(tag)
            finally:
                with self._lock:
                    self.percent.pop(tag, None)

        threading.Thread(target=work, name=f"download {tag}", daemon=True).start()


def listing(runtime: Runtime, downloads: Downloads) -> list[ModelInfo]:
    gateway = runtime.gateway
    try:
        installed = gateway.installed() if gateway else {}
    except DeskThreadError:
        installed = {}
    current = gateway.tag if gateway else config.MODEL_TAG
    return [
        ModelInfo(
            tag=m.tag,
            name=m.name,
            maker=m.maker,
            download_gb=m.download_gb,
            reads_pictures=m.reads_pictures,
            good_for=m.good_for,
            installed=m.tag in installed,
            selected=m.tag == current,
            tested=m.digest is not None,
            downloading=downloads.percent.get(m.tag),
            failed=m.tag in downloads.failed,
        )
        for m in config.MODELS
    ]


def register(app: FastAPI, runtime: Runtime) -> Downloads:
    downloads = Downloads()

    @app.get("/api/models")
    def models() -> list[ModelInfo]:
        return listing(runtime, downloads)

    @app.post("/api/models/select")
    def select(body: ModelPick) -> list[ModelInfo]:
        if runtime.gateway is None:
            raise DeskThreadError(ErrorCode.MODEL_UNAVAILABLE)
        with runtime.ask_lock:  # never in the middle of an answer
            runtime.gateway.select(body.tag)  # what was read stays in memory (user, 2026-11-22)
        return listing(runtime, downloads)

    @app.post("/api/models/download")
    def download(body: ModelPick) -> list[ModelInfo]:
        if config.model_choice(body.tag) is None:
            raise DeskThreadError(ErrorCode.BAD_REQUEST, "not an approved model")
        downloads.start(runtime, body.tag)
        return listing(runtime, downloads)

    return downloads
