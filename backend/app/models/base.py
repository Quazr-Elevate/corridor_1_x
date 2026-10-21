from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import ARRAY, JSON, DateTime
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator):
    """``DateTime(timezone=True)`` that always hands back aware UTC values.

    Postgres already returns aware datetimes; SQLite returns naive ones
    (stored as UTC). Normalising here keeps comparisons and API output
    identical on both dialects. Same DDL as ``DateTime(timezone=True)``.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value

    def process_result_value(self, value: datetime | None, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


class Base(DeclarativeBase):
    pass


def str_array(item_type):
    """Postgres ``ARRAY(item_type)`` in prod; a JSON list on SQLite (local
    dev / tests), which has no native array type. Same Python value
    (``list[str]``) either way."""
    return ARRAY(item_type).with_variant(JSON(), "sqlite")
