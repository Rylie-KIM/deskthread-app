"""The session clock.

DESKTHREAD_NOW (an ISO date-time) fixes "now" for tests and for the demo recording, where
the story is set on Sun 22 Nov 2026. It is a test-only setting and is declared in the README.
"""

import os
from datetime import UTC, datetime

ENV_NOW = "DESKTHREAD_NOW"


def now() -> datetime:
    fixed = os.environ.get(ENV_NOW)
    if fixed:
        value = datetime.fromisoformat(fixed)
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    return datetime.now(UTC)
