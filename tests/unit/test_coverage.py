"""U9: the coverage numbers add up, and out-of-reach material is counts only (FT-36)."""

from pathlib import Path

from app import coverage
from app.broker import Broker
from app.policy import AccessPolicy
from app.sources.folder import scan
from app.store import SessionStore
from contracts.broker import SourceStatus


def _session(root: Path) -> tuple[Broker, SessionStore]:
    broker = Broker()
    for adapter in scan(root, AccessPolicy([root])):
        broker.register(adapter)
    store = SessionStore(broker)
    for state in broker.states():
        if state.status is not SourceStatus.LOCKED:
            broker.grant(state.source_id, frozenset())
            store.load(state.source_id)
    return broker, store


def test_u9_accessible_is_searched_plus_unsupported(demo_laptop: Path) -> None:
    broker, store = _session(demo_laptop)
    cov = coverage.build(broker, store, given=9, cited=4)
    assert cov.accessible == cov.searched + cov.unsupported
    assert cov.accessible == sum(cov.by_source.values())
    assert cov.unsupported == 2  # the .heic and the .zip are counted, not skipped
    assert (cov.given_to_model, cov.cited) == (9, 4)
    assert cov.by_source["folder:notes"] == 21 and cov.by_source["folder:mail"] == 12


def test_u9_out_of_reach_material_is_counts_only(demo_laptop: Path) -> None:
    broker, store = _session(demo_laptop)
    cov = coverage.build(broker, store, given=0, cited=0)
    assert cov.not_accessible == {
        "WhatsApp": None,  # locked: not even counted
        "KakaoTalk": None,
        coverage.OFF_LIMITS_KEY: 4,  # the PRIVATE note and three files in Personal
    }
    broker.revoke("folder:notes")
    after = coverage.build(broker, store, given=0, cited=0)
    assert after.not_accessible["Notes"] == 21
    assert after.accessible == cov.accessible - 21 and "folder:notes" not in after.by_source
    broker.revoke_all()
    assert coverage.build(broker, store, given=0, cited=0).accessible == 0
