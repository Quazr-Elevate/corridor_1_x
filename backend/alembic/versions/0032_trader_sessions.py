"""Traders keep up to five sessions; company names are not unique

Revision ID: 0032_trader_sessions
Revises: 0031_desk_limits
Create Date: 2026-11-21

CX-155, decision A-044 (replaces the one-device part of A-008 for traders).

* ``user_sessions``: the partial unique index ``uq_user_sessions_one_active``
  becomes the plain partial index ``ix_user_sessions_active``. The limit of
  five lives in ``app/modules/auth/sessions.py``; admins keep their unique
  index and one session.
* ``business_identities``: ``uq_business_identities_legal_name_normalized``
  becomes the plain index ``ix_business_identities_legal_name_normalized``
  (CX-157, A-046). Sign-up no longer checks the name; the KYB review flags
  a business that shares one.

Portable (Postgres + SQLite). Reversible while no two businesses share a
name: the downgrade signs out all but each trader's newest live session and
restores both unique indexes (it fails if names are shared by then).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0032_trader_sessions"
down_revision: Union[str, None] = "0031_desk_limits"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OPEN = sa.text("revoked_at IS NULL")


def upgrade() -> None:
    op.drop_index("uq_user_sessions_one_active", table_name="user_sessions")
    op.create_index("ix_user_sessions_active", "user_sessions", ["user_id"], sqlite_where=OPEN, postgresql_where=OPEN)
    op.drop_index("uq_business_identities_legal_name_normalized", table_name="business_identities")
    op.create_index("ix_business_identities_legal_name_normalized", "business_identities", ["legal_name_normalized"])


def downgrade() -> None:
    op.drop_index("ix_business_identities_legal_name_normalized", table_name="business_identities")
    op.create_index(
        "uq_business_identities_legal_name_normalized", "business_identities", ["legal_name_normalized"], unique=True
    )
    op.execute(
        "UPDATE user_sessions SET revoked_at = CURRENT_TIMESTAMP, revoked_reason = 'replaced' "
        "WHERE revoked_at IS NULL AND id NOT IN ("
        "SELECT id FROM (SELECT id, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) AS n "
        "FROM user_sessions WHERE revoked_at IS NULL) AS ranked WHERE n = 1)"
    )
    op.drop_index("ix_user_sessions_active", table_name="user_sessions")
    op.create_index(
        "uq_user_sessions_one_active", "user_sessions", ["user_id"], unique=True, sqlite_where=OPEN, postgresql_where=OPEN
    )
