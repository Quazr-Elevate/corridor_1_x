"""businesses.verification_rejected_items — per-item blame list

Revision ID: 0023_reject_items
Revises: 0022_seed_doc_requirements
Create Date: 2026-10-30

Adds ``verification_rejected_items`` to businesses — a nullable JSON array
of keys like ``["fullName", "doc:business_registration"]`` populated when
admin rejects a business review. Lets the trader see exactly which fields
or docs need to be fixed before resubmitting; the free-text
``verification_rejected_reason`` carries the overall explanation.

Portable (Postgres uses JSONB via sa.JSON, SQLite uses TEXT via sa.JSON).
Reversible: downgrade drops the column.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023_reject_items"
down_revision: Union[str, None] = "0022_seed_doc_requirements"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("businesses") as batch:
        batch.add_column(sa.Column("verification_rejected_items", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("businesses") as batch:
        batch.drop_column("verification_rejected_items")
