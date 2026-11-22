"""Consent and instant revoke (FT-53, FT-15, FT-02, R15): the permission broker."""

import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.broker import Broker
from app.policy import AccessPolicy
from app.sources.folder import FolderAdapter, scan
from app.store import SessionStore
from contracts.adapters import ReadGrant
from contracts.broker import AuditAction, SourceStatus
from contracts.errors import DeskThreadError, ErrorCode
from contracts.items import Item, SourceKind, Uncounted


def _session(root: Path) -> tuple[Broker, SessionStore]:
    policy = AccessPolicy([root])
    broker = Broker()
    for adapter in scan(root, policy):
        broker.register(adapter)
    return broker, SessionStore(broker)


def _all_on(broker: Broker, store: SessionStore) -> None:
    for state in broker.states():
        broker.grant(state.source_id, frozenset())
        store.load(state.source_id)


def test_every_source_starts_off_and_cannot_be_read_before_it_is_allowed(
    demo_laptop: Path,
) -> None:
    broker, store = _session(demo_laptop)
    assert all(s.status is SourceStatus.OFF for s in broker.states())
    with pytest.raises(DeskThreadError) as err:
        store.load("folder:notes")
    assert err.value.code is ErrorCode.SOURCE_NOT_ALLOWED
    assert store.items() == []


def test_the_request_says_in_plain_words_what_will_be_read(demo_laptop: Path) -> None:
    broker, _ = _session(demo_laptop)
    request = broker.request("folder:mail")
    assert (
        "plain text" in request.what_will_be_read and "never fetched" in request.what_will_be_read
    )
    assert [(s.label, s.item_count) for s in request.scopes] == [("Mail", 12)]


def test_no_app_is_closed_for_good_a_chat_app_starts_off_and_can_be_allowed_for_reading(
    demo_laptop: Path,
) -> None:
    broker, store = _session(demo_laptop)
    scopes = {s.label: s.scope_id for s in broker.request("folder:chat-exports").scopes}
    assert {"WhatsApp", "KakaoTalk", "Teams", "Slack", "Zoom"} == set(scopes)
    assert not broker.is_allowed("folder:chat-exports") and store.items() == []  # Off until allowed
    broker.grant("folder:chat-exports", frozenset({scopes["WhatsApp"]}))
    assert store.load("folder:chat-exports") == 1
    assert "are you coming on Sunday" in store.items()[0].units[0].text
    broker.revoke("folder:chat-exports")
    assert store.items() == []


def test_reading_is_the_only_permission_there_is() -> None:
    """The broker has grant and revoke, and nothing that writes, sends or deletes."""
    public = {name for name in dir(Broker) if not name.startswith("_")}
    assert not {n for n in public if re.search("write|delete|send|modify|update|create", n)}
    assert {s.value for s in SourceStatus} == {"off", "on"}


def test_grant_then_revoke_leaves_zero_items_of_that_source(demo_laptop: Path) -> None:
    broker, store = _session(demo_laptop)
    broker.grant("folder:notes", frozenset())
    broker.grant("folder:mail", frozenset())
    assert store.load("folder:notes") == 21  # 22 files, the PRIVATE one is never read
    assert store.load("folder:mail") == 12
    state = broker.revoke("folder:notes")
    assert state.status is SourceStatus.OFF and state.items_in_memory == 0
    assert {i.source_id for i in store.items()} == {"folder:mail"}
    actions = [line.action for line in broker.audit()]
    assert actions.count(AuditAction.GRANT) == 2 and AuditAction.REVOKE in actions


def test_revoke_during_a_read_returns_zero_items(demo_laptop: Path) -> None:
    broker, store = _session(demo_laptop)
    broker.grant("folder:notes", frozenset())
    adapter = broker.adapter("folder:notes")
    seen = 0
    with pytest.raises(DeskThreadError) as err:
        for _ in adapter.read(broker.read_grant("folder:notes")):
            seen += 1
            if seen == 3:
                broker.revoke("folder:notes")  # the user clicks Stop mid-read
    assert err.value.code is ErrorCode.READ_CANCELLED and seen == 3

    class RevokesMidway(FolderAdapter):
        def read(self, grant: ReadGrant) -> Iterator[Item | Uncounted]:
            for count, thing in enumerate(super().read(grant)):
                if count == 2:
                    broker.revoke("folder:mail")
                yield thing

    broker.register(
        RevokesMidway(
            source_id="folder:mail",
            kind=SourceKind.MAIL,
            label="Mail",
            root=demo_laptop,
            scopes=[demo_laptop / "App-exports" / "Mail"],
            policy=AccessPolicy([demo_laptop]),
        )
    )
    broker.grant("folder:mail", frozenset())
    assert store.load("folder:mail") == 0
    assert store.items() == []


def test_stop_all_empties_every_source(demo_laptop: Path) -> None:
    broker, store = _session(demo_laptop)
    _all_on(broker, store)
    assert len(store.items()) > 40
    states = broker.revoke_all()
    assert all(s.status is not SourceStatus.ON for s in states)
    assert store.items() == [] and store.uncounted() == []
    assert broker.audit()[-1].action is AuditAction.REVOKE_ALL


def test_a_calendar_is_allowed_one_calendar_at_a_time(demo_laptop: Path) -> None:
    broker, store = _session(demo_laptop)
    scopes = {s.label: s.scope_id for s in broker.request("folder:calendar").scopes}
    broker.grant("folder:calendar", frozenset({scopes["work"]}))
    assert store.load("folder:calendar") == 12
    titles = {i.title for i in store.items()}
    assert "1:1 Sam" in titles and "Dentist" not in titles


def test_u1_with_every_source_on_private_material_is_still_not_in_memory(
    demo_laptop: Path,
) -> None:
    broker, store = _session(demo_laptop)
    _all_on(broker, store)
    text = "\n".join(u.text for item in store.items() for u in item.units)
    assert "Budget approved up to 800" in text
    for words in ("performance plan", "Tax return", "Landlord"):
        assert words not in text


def test_only_the_session_store_calls_read_on_an_adapter() -> None:
    """No path around the broker: adapter.read(grant) appears in app/ only in store.py."""
    app = Path(__file__).resolve().parents[2] / "app"
    callers = {
        p.name
        for p in app.rglob("*.py")
        if ".read(grant)" in p.read_text() and p.parent.name != "sources"  # adapters themselves
    }
    assert callers == {"store.py"}
