"""Putting a session together: policy, broker, store and assistant for a chosen folder."""

import re
from dataclasses import dataclass
from pathlib import Path

from app.assistant import Assistant
from app.broker import Broker
from app.model import Model
from app.policy import PERSONAL_CHAT_NAMES, AccessPolicy
from app.sources.folder import scan
from app.store import SessionStore


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


NOT_WORK = re.compile("personal|" + "|".join(sorted(PERSONAL_CHAT_NAMES)), re.I)


def work_profile(session: Session) -> None:
    """The work preset: work sources On; anything personal (a personal calendar, personal chat
    apps) stays Off. It is only a shortcut: the user can switch any source on by hand."""
    for state in session.broker.states():
        scopes = {s.scope_id for s in session.broker.request(state.source_id).scopes}
        scopes = {s for s in scopes if not NOT_WORK.search(s)}
        if scopes:
            session.broker.grant(state.source_id, frozenset(scopes))
