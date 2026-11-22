"""The stretch of time a grant covers, for sources where time matters (Calendar, Mail).

Either the last N days up to now, or an exact range of days chosen by the user (both days
included). Coming events are kept in the first case: `ahead_days` after now.
"""

from datetime import datetime, time, timedelta

from app.clock import now


def window(grant: object, default_days: int, ahead_days: int = 0) -> tuple[datetime, datetime]:
    since, until = getattr(grant, "since", None), getattr(grant, "until", None)
    moment = now()
    if since is not None:
        start = datetime.combine(since, time.min, moment.tzinfo)
        end = (
            datetime.combine(until, time.max, moment.tzinfo)
            if until is not None
            else moment + timedelta(days=ahead_days)
        )
        return start, end
    days = getattr(grant, "days", None) or default_days
    return moment - timedelta(days=days), moment + timedelta(days=ahead_days)
