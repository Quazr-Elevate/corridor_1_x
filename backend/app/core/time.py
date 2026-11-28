"""Timezone helpers.

SQLite hands back *naive* datetimes even for ``DateTime(timezone=True)``
columns (values are stored as UTC). Always pass DB datetimes through
:func:`ensure_aware` before comparing them with :func:`utcnow`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def ensure_aware(value: datetime | None) -> datetime | None:
    """Treat naive datetimes as UTC; leave aware ones untouched."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def add_business_days(start: datetime, days: int) -> datetime:
    """``start`` plus ``days`` weekdays (Monday to Friday), same time of day.
    Public holidays aren't counted out yet: which calendar (India, UAE or
    both) is for the client to confirm."""
    current, left = start, days
    while left > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            left -= 1
    return current
