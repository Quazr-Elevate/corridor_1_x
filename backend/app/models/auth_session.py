"""Server-side sessions and the sign-in event log.

The cookie carries a random token; only its SHA-256 is stored, so a
database leak doesn't hand out live sessions. A partial unique index keeps
**one active session per account**: signing in elsewhere revokes the old
one first (``revoked_reason = 'replaced'``).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CHAR, JSON, ForeignKey, Index, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime


class _SessionColumns:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    # Refreshed at most once a minute; idle expiry = last_seen_at + idle TTL.
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)  # absolute cap
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    # logout | replaced | logout_all | password_changed | password_reset |
    # account_deleted | admin_revoked | account_disabled
    revoked_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Truncated client IP (IPv4 /24, IPv6 /48) — never the full address.
    ip_prefix: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(200), nullable=True)


class UserSession(_SessionColumns, Base):
    __tablename__ = "user_sessions"
    __table_args__ = (
        Index("uq_user_sessions_token_hash", "token_hash", unique=True),
        Index(
            "uq_user_sessions_one_active",
            "user_id",
            unique=True,
            sqlite_where=text("revoked_at IS NULL"),
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index("ix_user_sessions_user", "user_id", text("created_at DESC")),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE", name="fk_user_sessions_user_id"), nullable=False
    )


class AdminSession(_SessionColumns, Base):
    __tablename__ = "admin_sessions"
    __table_args__ = (
        Index("uq_admin_sessions_token_hash", "token_hash", unique=True),
        Index(
            "uq_admin_sessions_one_active",
            "admin_user_id",
            unique=True,
            sqlite_where=text("revoked_at IS NULL"),
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index("ix_admin_sessions_admin", "admin_user_id", text("created_at DESC")),
    )

    admin_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("admin_users.id", ondelete="CASCADE", name="fk_admin_sessions_admin_user_id"), nullable=False
    )


class AuthEvent(Base):
    """Security log: sign-ins, failures, lockouts, logouts, password events.

    ``subject_type`` is ``user`` | ``admin``; ``subject_id`` is null for a
    failed sign-in with an unknown email (the email itself is not stored).
    """

    __tablename__ = "auth_events"
    __table_args__ = (
        Index("ix_auth_events_subject", "subject_type", "subject_id", text("created_at DESC")),
        Index("ix_auth_events_created_at", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    subject_type: Mapped[str] = mapped_column(String(10), nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    # login_succeeded | login_failed | locked | locked_support | unlocked |
    # logout | session_replaced | sessions_revoked | password_changed |
    # password_reset_requested | password_reset
    event: Mapped[str] = mapped_column(String(40), nullable=False)
    ip_prefix: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(200), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
