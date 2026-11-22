"""Coverage for every answer (FT-36): what was within reach, what was searched, what the
model was shown, what was cited, and what was out of reach. Counts only.

accessible = searched + unsupported, and cited is never more than given_to_model (test U9).
"""

from app.broker import Broker
from app.sources.folder import FolderAdapter
from app.store import SessionStore
from contracts.api import Coverage
from contracts.broker import SourceStatus

OFF_LIMITS_KEY = "off-limits (never read)"


def off_limits(broker: Broker) -> int:
    """Files in allowed sources that the policy keeps out of reach. Never opened."""
    total = 0
    for state in broker.states():
        adapter = broker.adapter(state.source_id)
        if state.status is SourceStatus.ON and isinstance(adapter, FolderAdapter):
            total += adapter.off_limits_count()
    return total


def build(broker: Broker, store: SessionStore, given: int, cited: int) -> Coverage:
    items, uncounted = store.items(), store.uncounted()
    by_source: dict[str, int] = {}
    for item in items:
        by_source[item.source_id] = by_source.get(item.source_id, 0) + 1
    for miss in uncounted:
        by_source[miss.source_id] = by_source.get(miss.source_id, 0) + 1
    not_accessible: dict[str, int | None] = {}
    for state in broker.states():
        if state.status is SourceStatus.LOCKED:
            not_accessible[state.label] = None  # locked: not even counted
        elif state.status is SourceStatus.OFF:
            scopes = broker.adapter(state.source_id).list_scopes()  # names and counts only
            not_accessible[state.label] = sum(s.item_count or 0 for s in scopes)
    not_accessible[OFF_LIMITS_KEY] = off_limits(broker)
    return Coverage(
        accessible=len(items) + len(uncounted),
        searched=len(items),
        unsupported=len(uncounted),
        given_to_model=given,
        cited=cited,
        by_source=by_source,
        not_accessible=not_accessible,
    )
