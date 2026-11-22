"""The local HTTP API (FT-23, FT-42): the only door between the page and the backend.

Every request must come to 127.0.0.1 on our port (Host check), from our own page (Origin
check) and carry this launch's token. Every reply says "do not store" and carries a strict
content-security-policy, so the page can load nothing from outside. Note text is returned as
plain strings and shown as text, never as HTML.
"""

import base64
import hashlib
import hmac
import mimetypes
import re
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import contracts
from app import config, models
from app.clock import now
from app.icons import APPS, app_icon, show_original
from app.proof import ending, evidence, memory
from app.runtime import Runtime
from app.sources.folder import kinds_in
from contracts.api import (
    TOKEN_HEADER,
    Answer,
    ApiError,
    AskBody,
    FolderChoice,
    FolderInfo,
    GrantBody,
    ItemView,
    Meeting,
    PrepareBody,
    Progress,
    SessionInfo,
    UnitView,
)
from contracts.broker import PermissionRequest, SourceState
from contracts.errors import DeskThreadError, ErrorCode
from contracts.items import Item, ItemKind

_INLINE_SCRIPT = re.compile(
    rb"<script(?![^>]*\bsrc=)(?![^>]*application/json)[^>]*>(.*?)</script>", re.S
)


def script_hashes(ui_dir: Path | None) -> list[str]:
    """Hashes of the inline scripts in our own built page. The build tool puts one small
    start-up script inline; allowing it by its exact hash keeps every other inline script
    (for example one smuggled in through a note) blocked."""
    hashes: set[str] = set()
    if ui_dir is not None and ui_dir.is_dir():
        for page in sorted(ui_dir.glob("*.html")):
            for body in _INLINE_SCRIPT.findall(page.read_bytes()):
                digest = base64.b64encode(hashlib.sha256(body).digest()).decode()
                hashes.add(f"'sha256-{digest}'")
    return sorted(hashes)


def content_security_policy(ui_dir: Path | None = None) -> str:
    scripts = " ".join(["'self'", *script_hashes(ui_dir)])
    return (
        f"default-src 'none'; script-src {scripts}; style-src 'self' 'unsafe-inline'; "
        "img-src 'self'; connect-src 'self'; font-src 'self'; base-uri 'none'; "
        "form-action 'none'; frame-ancestors 'none'"
    )


SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-origin",
}
STATUS = {
    ErrorCode.BAD_TOKEN: 401,
    ErrorCode.BAD_ORIGIN: 403,
    ErrorCode.BAD_HOST: 400,
    ErrorCode.BAD_REQUEST: 400,
    ErrorCode.SOURCE_UNKNOWN: 404,
    ErrorCode.SOURCE_LOCKED: 403,
    ErrorCode.SOURCE_NOT_ALLOWED: 409,
    ErrorCode.ITEM_OFF_LIMITS: 403,
    ErrorCode.PATH_OUTSIDE_ALLOWED: 403,
    ErrorCode.MODEL_UNAVAILABLE: 503,
}


def _error(code: ErrorCode, message: str = "") -> JSONResponse:
    body = ApiError(code=code.value, message=message or code.name.replace("_", " ").lower())
    return JSONResponse(body.model_dump(), status_code=STATUS.get(code, 500))


def create_app(runtime: Runtime, ui_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="DeskThread", version=contracts.CONTRACT_VERSION, docs_url=None,
                  redoc_url=None, openapi_url=None)  # fmt: skip

    # The policy follows the built page: if the page is rebuilt while the app runs, the hash
    # of its start-up script changes, so it is worked out again when the page file changes.
    built: dict[str, object] = {"stamp": None, "csp": content_security_policy(ui_dir)}

    def current_policy() -> str:
        page = ui_dir / "index.html" if ui_dir is not None else None
        stamp = page.stat().st_mtime_ns if page is not None and page.is_file() else None
        if stamp != built["stamp"]:
            built["stamp"], built["csp"] = stamp, content_security_policy(ui_dir)
        return str(built["csp"])

    @app.middleware("http")
    async def guard(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response: Response
        host = request.headers.get("host", "")
        origin = request.headers.get("origin")
        if host != f"127.0.0.1:{runtime.port}":
            response = _error(ErrorCode.BAD_HOST)  # stops DNS-rebinding tricks
        elif origin is not None and origin != runtime.origin:
            response = _error(ErrorCode.BAD_ORIGIN)  # another site cannot call us
        elif request.url.path.startswith("/api/") and not _token_ok(request, runtime):
            response = _error(ErrorCode.BAD_TOKEN)
        else:
            response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers[name] = value
        response.headers["Content-Security-Policy"] = current_policy()
        return response

    @app.exception_handler(DeskThreadError)
    async def coded(_: Request, err: DeskThreadError) -> JSONResponse:
        return _error(err.code, err.message)

    # ------------------------------------------------------------------ session and sources
    @app.get("/api/session")
    def session_info() -> SessionInfo:
        return SessionInfo(
            contract_version=contracts.CONTRACT_VERSION,
            model_tag=runtime.gateway.tag if runtime.gateway else config.MODEL_TAG,
            model_digest=(runtime.gateway.digest if runtime.gateway else "") or config.MODEL_DIGEST,
            prompt_version=config.PROMPT_VERSION,
            now=now(),
            demo_folder=str(runtime.demo_folder) if runtime.demo_folder else "",
        )

    @app.get("/api/sources")
    def sources() -> list[SourceState]:
        return runtime.session.broker.states() if runtime.session else []

    @app.post("/api/folder")
    def folder(body: FolderChoice) -> list[SourceState]:
        return runtime.choose(body.path).broker.states()

    @app.get("/api/folders")
    def folders() -> list[FolderInfo]:
        return [FolderInfo(path=str(f), name=f.name, **kinds_in(f)) for f in runtime.folders]

    @app.post("/api/folder/remove")
    def remove_folder(body: FolderChoice) -> list[SourceState]:
        return runtime.remove(body.path).broker.states()

    @app.get("/api/sources/{source_id}/request")
    def permission_request(source_id: str) -> PermissionRequest:
        return runtime.require().broker.request(source_id)

    @app.post("/api/sources/revoke-all")
    def revoke_all() -> list[SourceState]:
        return runtime.require().broker.revoke_all()

    @app.post("/api/sources/{source_id}/grant")
    def grant(source_id: str, body: GrantBody) -> SourceState:
        session = runtime.require()
        if body.since and body.until and body.since > body.until:
            raise DeskThreadError(ErrorCode.BAD_REQUEST)
        session.broker.grant(
            source_id, frozenset(body.scope_ids), body.days, body.since, body.until
        )
        session.store.load(source_id)
        return next(s for s in session.broker.states() if s.source_id == source_id)

    @app.get("/api/sources/{source_id}/icon")
    def icon(source_id: str) -> Response:
        data = app_icon(source_id)
        if data is None:
            raise DeskThreadError(ErrorCode.SOURCE_UNKNOWN)
        return Response(content=data, media_type="image/png")

    @app.post("/api/sources/{source_id}/revoke")
    def revoke(source_id: str) -> SourceState:
        return runtime.require().broker.revoke(source_id)  # immediate; never queued

    # ------------------------------------------------------------------ questions
    @app.get("/api/meetings")
    def meetings() -> list[Meeting]:
        return runtime.session.assistant.meetings() if runtime.session else []

    @app.post("/api/prepare")
    def prepare(body: PrepareBody) -> Answer:
        with runtime.ask_lock:
            return runtime.require().assistant.prepare(body.meeting_id)

    @app.get("/api/progress")
    def progress() -> Progress:
        return runtime.session.assistant.progress  # never waits for the running question

    @app.post("/api/cancel")
    def cancel() -> Progress:
        runtime.session.assistant.cancel()  # never waits for the running question
        return runtime.session.assistant.progress

    @app.post("/api/ask")
    def ask(body: AskBody) -> Answer:
        with runtime.ask_lock:
            return runtime.require().assistant.ask(body.question)

    # ------------------------------------------------------------------ the source viewer
    def _view(found: Item) -> ItemView:
        labels = {s.source_id: s.label for s in runtime.require().broker.states()}
        origin = "file" if found.meta.get("path") else "app" if found.source_id in APPS else ""
        return ItemView(
            item_id=found.item_id,
            source_label=labels.get(found.source_id, found.source_id),
            kind=found.kind.value,
            title=found.title,
            date=found.date,
            location=found.location,
            units=tuple(UnitView(number=u.number, text=u.text) for u in found.units),
            read_by_model=found.read_by_model,
            has_image=found.kind is ItemKind.IMAGE,
            origin=origin,
        )

    def _visible(item_id: str) -> Item:
        found = runtime.require().store.get(item_id)  # only items of sources that are On now
        if found is None:
            raise DeskThreadError(ErrorCode.SOURCE_NOT_ALLOWED, "not visible")
        return found

    @app.get("/api/items/{item_id}")
    def item(item_id: str) -> ItemView:
        return _view(_visible(item_id))

    @app.post("/api/items/{item_id}/reveal")
    def reveal(item_id: str) -> ItemView:
        """Show the original to the user. The path is the item's own, checked again (G1);
        the page cannot name a path."""
        found = _visible(item_id)
        path = found.meta.get("path")
        real = runtime.require().policy.check_read(Path(path)) if path else None
        if not show_original(found.source_id, real, found.meta, found.date):
            raise DeskThreadError(ErrorCode.BAD_REQUEST)
        return _view(found)

    @app.get("/api/items/{item_id}/image")
    def image(item_id: str) -> Response:
        session = runtime.require()
        found = session.store.get(item_id)
        if found is None or found.kind is not ItemKind.IMAGE:
            raise DeskThreadError(ErrorCode.SOURCE_NOT_ALLOWED, "not visible")
        real = session.policy.check_read(Path(found.meta["path"]))  # G1 again, on the real path
        with real.open("rb") as handle:
            data = handle.read()
        kind = mimetypes.guess_type(real.name)[0] or "application/octet-stream"
        return Response(content=data, media_type=kind)

    models.register(app, runtime)
    memory.register(app, runtime)
    ending.register(app, runtime, evidence.register(app, runtime))

    if ui_dir is not None and ui_dir.is_dir():
        app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
    return app


def _token_ok(request: Request, runtime: Runtime) -> bool:
    sent = request.headers.get(TOKEN_HEADER, "")
    if not sent and request.url.path.endswith(("/image", "/icon")):
        sent = request.query_params.get("t", "")  # an <img> tag cannot send a header
    return hmac.compare_digest(sent.encode(), runtime.token.encode())
