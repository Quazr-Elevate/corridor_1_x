"""One-shot temporary password issued at signup / resend.

Replaces the magic-link email verification flow with a simple
credential handoff:

  1. Signup creates a row here holding a bcrypt hash of a 12-char
     random password, 24h expiry, zero attempts.
  2. The plaintext password is emailed to the user.
  3. On login, if the user has no real ``users.password_hash`` yet, we
     verify against this table and set ``users.must_change_password``.
  4. The row is marked consumed on first successful login and deleted
     when the user sets a real password in /dashboard/settings/password.

One active row per user — resending a credential clobbers any
outstanding one so the previously-emailed password stops working.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TempCredential(Base):
    __tablename__ = "temp_credentials"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # UNIQUE so a resend overwrites, not accumulates. Deletes cascade
    # from the user row when the account is removed.
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # bcrypt hash of the 12-char URL-safe random password. Never store
    # the plaintext — same discipline as regular passwords.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # Capped at 5 — on exhaustion we invalidate the row so a stolen
    # 12-char password isn't brute-forceable even with a long window.
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
