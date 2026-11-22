"""Putting a session together: policy, broker, store and assistant for a chosen folder."""

from dataclasses import dataclass
from pathlib import Path

from app.assistant import Assistant
from app.broker import Broker
from app.model import Model
from app.policy import AccessPolicy
from app.sources.folder import scan
from app.store import SessionStore
from contracts.broker import SourceStatus
from contracts.items import SourceKind


@dataclass
class Session:
    policy: AccessPolicy
    broker: Broker
    store: SessionStore
    assistant: Assistant


def open_folder(root: Path, model: Model) -> Session:
    """A new session on one folder. Every source starts Off."""
    policy = AccessPolicy([root])
    broker = Broker()
    for adapter in scan(root, policy):
        broker.register(adapter)
    store = SessionStore(broker)
    return Session(policy, broker, store, Assistant(broker, store, policy, model))


def work_profile(session: Session) -> None:
    """The "Work profile" preset: work sources On; a calendar called Personal stays Off."""
    for state in session.broker.states():
        if state.status is SourceStatus.LOCKED:
            continue
        scopes = {s.scope_id for s in session.broker.request(state.source_id).scopes}
        if state.kind is SourceKind.CALENDAR:
            scopes = {s for s in scopes if "personal" not in s.lower()}
        if scopes:
            session.broker.grant(state.source_id, frozenset(scopes))
