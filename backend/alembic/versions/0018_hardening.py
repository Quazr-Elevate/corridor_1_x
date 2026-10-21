"""hardening: session_version, normalized unique keys, admin_actions

Revision ID: 0018_hardening
Revises: 0017_temp_credentials
Create Date: 2026-10-15

* ``users.session_version`` (int, default 0) — embedded in the session
  cookie; bumping it revokes every outstanding session.
* ``profiles.phone_normalized``, ``business_profiles.legal_name_normalized``
  and ``business_profiles.website_normalized`` + UNIQUE indexes — moves the
  "already registered" checks from racy Python scans into the database.
  Backfilled here; when existing rows already collide, the OLDEST row keeps
  the key and later duplicates are left NULL (logged) so the index can be
  created without failing the deploy.
* ``admin_actions`` — audit trail for admin verify/reject/edit actions.

Portable: runs on Postgres and SQLite (batch ops; Python backfill).
"""
from __future__ import annotations

import logging
import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018_hardening"
down_revision: Union[str, None] = "0017_temp_credentials"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

log = logging.getLogger("alembic.runtime.migration")

# ── Frozen copies of app/shared/normalize.py (migrations must not import
#    app code that may change later). ────────────────────────────────────
_WS = re.compile(r"\s+")
_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*://")


def _norm_phone(raw):
    if not raw:
        return None
    out = "".join(ch for ch in raw if ch.isdigit() or ch == "+")
    return out or None


def _norm_legal_name(raw):
    if not raw:
        return None
    out = _WS.sub(" ", raw.strip()).lower()
    return out or None


def _norm_website(raw):
    if not raw:
        return None
    s = _SCHEME.sub("", raw.strip().lower())
    s = s.split("#", 1)[0].split("?", 1)[0]
    if s.startswith("www."):
        s = s[4:]
    s = s.rstrip("/")
    return s or None


def _backfill(bind, table: sa.Table, source: str, target: str, fn) -> None:
    rows = bind.execute(
        sa.select(table.c.id, table.c[source])
        .where(table.c[source].is_not(None))
        .order_by(table.c.created_at, table.c.id)
    ).all()
    seen: set[str] = set()
    skipped = 0
    for row_id, value in rows:
        key = fn(value)
        if key is None:
            continue
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        bind.execute(sa.update(table).where(table.c.id == row_id).values({target: key}))
    if skipped:
        log.warning("0018: %d duplicate %s.%s value(s) left NULL", skipped, table.name, target)


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("session_version", sa.Integer(), nullable=False, server_default=sa.text("0"))
        )
    with op.batch_alter_table("profiles") as batch:
        batch.add_column(sa.Column("phone_normalized", sa.String(length=20), nullable=True))
    with op.batch_alter_table("business_profiles") as batch:
        batch.add_column(sa.Column("legal_name_normalized", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("website_normalized", sa.String(length=300), nullable=True))

    if not op.get_context().as_sql:  # offline (--sql) mode can't read rows
        bind = op.get_bind()
        meta = sa.MetaData()
        profiles = sa.Table(
            "profiles",
            meta,
            sa.Column("id", sa.Uuid()),
            sa.Column("phone", sa.String(20)),
            sa.Column("phone_normalized", sa.String(20)),
            sa.Column("created_at", sa.DateTime(timezone=True)),
        )
        businesses = sa.Table(
            "business_profiles",
            meta,
            sa.Column("id", sa.Uuid()),
            sa.Column("legal_name", sa.String(200)),
            sa.Column("website_url", sa.String(300)),
            sa.Column("legal_name_normalized", sa.String(200)),
            sa.Column("website_normalized", sa.String(300)),
            sa.Column("created_at", sa.DateTime(timezone=True)),
        )
        _backfill(bind, profiles, "phone", "phone_normalized", _norm_phone)
        _backfill(bind, businesses, "legal_name", "legal_name_normalized", _norm_legal_name)
        _backfill(bind, businesses, "website_url", "website_normalized", _norm_website)

    op.create_index("uq_profiles_phone_normalized", "profiles", ["phone_normalized"], unique=True)
    op.create_index(
        "uq_business_profiles_legal_name_normalized", "business_profiles", ["legal_name_normalized"], unique=True
    )
    op.create_index(
        "uq_business_profiles_website_normalized", "business_profiles", ["website_normalized"], unique=True
    )

    op.create_table(
        "admin_actions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("admin_email", sa.String(length=200), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("target_type", sa.String(length=30), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_admin_actions_target", "admin_actions", ["target_type", "target_id"])
    op.create_index("ix_admin_actions_created_at", "admin_actions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_admin_actions_created_at", table_name="admin_actions")
    op.drop_index("ix_admin_actions_target", table_name="admin_actions")
    op.drop_table("admin_actions")
    op.drop_index("uq_business_profiles_website_normalized", table_name="business_profiles")
    op.drop_index("uq_business_profiles_legal_name_normalized", table_name="business_profiles")
    op.drop_index("uq_profiles_phone_normalized", table_name="profiles")
    with op.batch_alter_table("business_profiles") as batch:
        batch.drop_column("website_normalized")
        batch.drop_column("legal_name_normalized")
    with op.batch_alter_table("profiles") as batch:
        batch.drop_column("phone_normalized")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("session_version")
