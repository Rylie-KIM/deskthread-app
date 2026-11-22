"""Putting a session together: policy, broker, store and assistant for a chosen folder."""

import re
from dataclasses import dataclass
from pathlib import Path

from app import ocr
from app.assistant import Assistant
from app.broker import Broker
from app.model import Model
from app.policy import PERSONAL_CHAT_NAMES, AccessPolicy
from app.sources.folder import scan_all
from app.store import SessionStore
from contracts.adapters import SourceAdapter
from contracts.broker import SourceStatus
from contracts.errors import DeskThreadError
from contracts.items import SourceKind


@dataclass
class Session:
    policy: AccessPolicy
    broker: Broker
    store: SessionStore
    assistant: Assistant


def new_session(model: Model, apps: list[SourceAdapter] | None = None) -> Session:
    """A new session with no folder chosen yet. Apps on this Mac are listed, all Off."""
    policy = AccessPolicy([])
    broker = Broker()
    for adapter in apps or []:
        broker.register(adapter)
    store = SessionStore(broker)

    def blocked(adapter: SourceAdapter) -> str:
        # Asked each time, so choosing another AI model changes it at once.
        # macOS reads the text of pictures for any answering AI; only without it does the
        # answering AI have to read them itself.
        if (
            adapter.kind is SourceKind.IMAGES
            and not ocr.available()
            and not getattr(model, "reads_pictures", True)
        ):
            return "This AI model does not read pictures"
        return ""

    broker.set_blocker(blocked)
    return Session(policy, broker, store, Assistant(broker, store, policy, model))


def set_folders(session: Session, roots: list[Path]) -> None:
    """Use exactly these folders. Sources that were On stay On for the parts that still
    exist; a folder that was removed leaves memory at once."""
    kept = {
        state.source_id: frozenset(state.allowed_scope_ids)
        for state in session.broker.states()
        if state.source_id.startswith("folder:") and state.status is SourceStatus.ON
    }
    session.policy.set_roots(roots)
    session.broker.replace("folder:", list(scan_all(roots, session.policy)))
    for source_id, scopes in kept.items():
        try:
            still = {s.scope_id for s in session.broker.request(source_id).scopes} & scopes
        except DeskThreadError:
            continue  # that kind of source is gone with its folder
        if still:
            session.broker.grant(source_id, frozenset(still))
            session.store.load(source_id)


def choose_folder(session: Session, root: Path) -> None:
    """Add a folder. Its sources start Off."""
    roots = session.policy.roots
    if root.resolve() not in roots:
        set_folders(session, [*roots, root.resolve()])
        session.broker.note_folder(True, root.resolve().name)


def remove_folder(session: Session, root: Path) -> None:
    if root.resolve() in session.policy.roots:
        set_folders(session, [r for r in session.policy.roots if r != root.resolve()])
        session.broker.note_folder(False, root.resolve().name)


def open_folder(root: Path, model: Model) -> Session:
    """A new session on one folder. Every source starts Off."""
    session = new_session(model)
    choose_folder(session, root)
    return session


NOT_WORK = re.compile("personal|" + "|".join(sorted(PERSONAL_CHAT_NAMES)), re.I)


def work_profile(session: Session) -> None:
    """The work preset: work sources On; anything personal (a personal calendar, personal chat
    apps) stays Off. It is only a shortcut: the user can switch any source on by hand."""
    for state in session.broker.states():
        scopes = {s.scope_id for s in session.broker.request(state.source_id).scopes}
        scopes = {s for s in scopes if not NOT_WORK.search(s)}
        if scopes:
            session.broker.grant(state.source_id, frozenset(scopes))
