"""Append-only audit trail of admin console actions."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Index, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime


class AdminAction(Base):
    """One row per admin decision / edit.

    ``action``      — ``business.verify``, ``business.reject``,
                      ``business.update``, ``doc.approve``, ``doc.reject``.
    ``target_type`` — ``business`` | ``user`` | ``document``; ``target_id`` is
                      the target's UUID as text (no FK, so new target kinds
                      need no migration).
    ``details``     — small JSON payload (e.g. edited field names).
    """

    __tablename__ = "admin_actions"
    __table_args__ = (
        Index("ix_admin_actions_target", "target_type", "target_id", text("created_at DESC")),
        Index("ix_admin_actions_created_at", text("created_at DESC")),
        Index("ix_admin_actions_admin", "admin_email", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    admin_email: Mapped[str] = mapped_column(String(200), nullable=False)
    # Null for rows written before named admin accounts (0024).
    admin_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("admin_users.id", ondelete="SET NULL", name="fk_admin_actions_admin_user_id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )
