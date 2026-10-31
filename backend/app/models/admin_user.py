"""Named admin-console accounts (replaces the single env-password admin)."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Enum, Index, Integer, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime


class AdminRole(str, enum.Enum):
    """What an admin may do — see ``app/modules/admin/permissions.py``."""

    super_admin = "super_admin"
    reviewer = "reviewer"


class AdminStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"


class AdminUser(Base):
    """One person who signs in to the admin console.

    The first super admin is bootstrapped from ``ADMIN_EMAIL`` /
    ``ADMIN_PASSWORD_HASH`` while this table is empty; after that, super
    admins create the others (temporary password, changed on first login).
    Lockout counters mirror the ones on ``users``.
    """

    __tablename__ = "admin_users"
    __table_args__ = (
        Index("uq_admin_users_email", "email", unique=True),
        CheckConstraint("email = lower(email)", name="ck_admin_users_email_lowercase"),
        CheckConstraint("failed_login_count >= 0", name="ck_admin_users_failed_login_count"),
        CheckConstraint("lockout_count >= 0", name="ck_admin_users_lockout_count"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[AdminRole] = mapped_column(Enum(AdminRole, name="admin_role"), nullable=False)
    status: Mapped[AdminStatus] = mapped_column(
        Enum(AdminStatus, name="admin_status"), nullable=False, default=AdminStatus.active,
        server_default=AdminStatus.active.value,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Set for accounts created with a temporary password: only
    # /admin/change-password works until it is changed.
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    password_changed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    # ─── Lockout (app/modules/auth/lockout.py) ──────────────────
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    lockout_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )
