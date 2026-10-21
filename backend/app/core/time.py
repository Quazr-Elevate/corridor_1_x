"""Timezone helpers.

SQLite hands back *naive* datetimes even for ``DateTime(timezone=True)``
columns (values are stored as UTC). Always pass DB datetimes through
:func:`ensure_aware` before comparing them with :func:`utcnow`.
"""
from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def ensure_aware(value: datetime | None) -> datetime | None:
    """Treat naive datetimes as UTC; leave aware ones untouched."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
