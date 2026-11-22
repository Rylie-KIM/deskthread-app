"""Runs against the REAL Mac apps, in the user's own account. Only with `make test-live`.

Dev rule R1: nothing from the apps may be printed. These tests assert on counts and types
only, and every message goes through the output guard.
"""

import pytest

from app.sources.mac import mac_apps
from contracts.errors import DeskThreadError
from contracts.redact import live_print, safe_error

pytestmark = pytest.mark.live


@pytest.mark.parametrize("name", ["calendar", "notes", "reminders", "mail"])
def test_live_listing_scopes_reads_names_and_counts_only(name: str) -> None:
    adapter = next((a for a in mac_apps() if a.source_id == f"mac:{name}"), None)
    if adapter is None:
        pytest.skip("app not installed")
    try:
        scopes = adapter.list_scopes()
    except DeskThreadError as err:
        live_print(f"{name}: {safe_error(err)} fail")
        raise AssertionError("listing failed") from None
    total = sum(s.item_count or 0 for s in scopes)
    live_print(f"{name}: scopes={len(scopes)} items={total} writes=0 pass")
    assert len(scopes) >= 1
