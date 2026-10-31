"""Phase A identity & access: named admins, server-side sessions, lockout,
sign-in events

Revision ID: 0024_identity_access
Revises: 0023_countries
Create Date: 2026-10-31

Implements docs/04_data_model.md → "Identity & access (0024)":

* ``admin_users`` — named admin accounts (super_admin | reviewer), temporary
  password flag, lockout counters. Empty after upgrade: the first sign-in
  with ``ADMIN_EMAIL`` / ``ADMIN_PASSWORD_HASH`` creates the super admin.
* ``user_sessions`` / ``admin_sessions`` — server-side sessions (token
  SHA-256, idle + absolute expiry, truncated IP, user agent) with a partial
  unique index: one active session per account.
* ``auth_events`` — sign-in / lockout / logout / password events.
* ``users`` — ``failed_login_count``, ``lockout_count``, ``locked_until``.
* ``admin_actions.admin_user_id`` — FK to the acting admin (null for older rows).

Every signed cookie issued before this revision stops working (users sign in
again). Portable (Postgres + SQLite batch ops). Reversible.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024_identity_access"
down_revision: Union[str, None] = "0023_countries"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACTIVE = sa.text("revoked_at IS NULL")


def _session_table(name: str, owner_col: str, owner_table: str, fk_name: str) -> None:
    op.create_table(
        name,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(owner_col, sa.Uuid(), sa.ForeignKey(f"{owner_table}.id", ondelete="CASCADE", name=fk_name), nullable=False),
        sa.Column("token_hash", sa.CHAR(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(30), nullable=True),
        sa.Column("ip_prefix", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(200), nullable=True),
    )
    short = name.removesuffix("s")  # user_session / admin_session
    op.create_index(f"uq_{name}_token_hash", name, ["token_hash"], unique=True)
    op.create_index(
        f"uq_{name}_one_active", name, [owner_col], unique=True, sqlite_where=ACTIVE, postgresql_where=ACTIVE
    )
    op.create_index(f"ix_{name}_{short.split('_')[0]}", name, [owner_col, sa.text("created_at DESC")])


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("full_name", sa.String(100), nullable=False),
        sa.Column("role", sa.Enum("super_admin", "reviewer", name="admin_role"), nullable=False),
        sa.Column("status", sa.Enum("active", "disabled", name="admin_status"), nullable=False, server_default="active"),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lockout_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("email = lower(email)", name="ck_admin_users_email_lowercase"),
        sa.CheckConstraint("failed_login_count >= 0", name="ck_admin_users_failed_login_count"),
        sa.CheckConstraint("lockout_count >= 0", name="ck_admin_users_lockout_count"),
    )
    op.create_index("uq_admin_users_email", "admin_users", ["email"], unique=True)

    _session_table("user_sessions", "user_id", "users", "fk_user_sessions_user_id")
    _session_table("admin_sessions", "admin_user_id", "admin_users", "fk_admin_sessions_admin_user_id")

    op.create_table(
        "auth_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("subject_type", sa.String(10), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=True),
        sa.Column("event", sa.String(40), nullable=False),
        sa.Column("ip_prefix", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(200), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_auth_events_subject", "auth_events", ["subject_type", "subject_id", sa.text("created_at DESC")])
    op.create_index("ix_auth_events_created_at", "auth_events", [sa.text("created_at DESC")])

    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("lockout_count", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
        batch.create_check_constraint("ck_users_failed_login_count", "failed_login_count >= 0")
        batch.create_check_constraint("ck_users_lockout_count", "lockout_count >= 0")

    with op.batch_alter_table("admin_actions") as batch:
        batch.add_column(sa.Column("admin_user_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_admin_actions_admin_user_id", "admin_users", ["admin_user_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    with op.batch_alter_table("admin_actions") as batch:
        batch.drop_constraint("fk_admin_actions_admin_user_id", type_="foreignkey")
        batch.drop_column("admin_user_id")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("ck_users_lockout_count", type_="check")
        batch.drop_constraint("ck_users_failed_login_count", type_="check")
        batch.drop_column("locked_until")
        batch.drop_column("lockout_count")
        batch.drop_column("failed_login_count")
    op.drop_table("auth_events")
    op.drop_table("admin_sessions")
    op.drop_table("user_sessions")
    op.drop_table("admin_users")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS admin_status")
        op.execute("DROP TYPE IF EXISTS admin_role")
