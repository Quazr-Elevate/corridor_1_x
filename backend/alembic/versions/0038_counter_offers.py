"""Counter-offers: structured price changes through the desk

Revision ID: 0038_counter_offers
Revises: 0037_negotiation_chat
Create Date: 2026-11-26

M4 · S8, CX-101 (A-078); docs/04_data_model.md → "Counter-offers (0038)".

* new ``counter_offers``: one side's proposed price in its own currency, the
  price it implies for the other side (back-solved through the deal's cost
  sheet), the margin used, and where it stands.

No existing rows change. Portable. Reversible: downgrade drops the table.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0038_counter_offers"
down_revision: Union[str, None] = "0037_negotiation_chat"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STATUSES = "('pending_desk', 'relayed', 'accepted', 'declined', 'rejected', 'superseded')"


def upgrade() -> None:
    op.create_table(
        "counter_offers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=False),
        sa.Column("side", sa.String(6), nullable=False),
        sa.Column("price_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("implied_minor", sa.BigInteger(), nullable=False),
        sa.Column("implied_currency", sa.CHAR(3), nullable=False),
        sa.Column("margin_pct", sa.Numeric(6, 2), nullable=False),
        sa.Column("status", sa.String(14), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_note", sa.String(500), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("side IN ('buyer', 'seller')", name="ck_counter_offers_side"),
        sa.CheckConstraint(f"status IN {STATUSES}", name="ck_counter_offers_status"),
        sa.CheckConstraint("price_minor > 0 AND implied_minor > 0", name="ck_counter_offers_prices"),
        sa.CheckConstraint("quantity IS NULL OR quantity > 0", name="ck_counter_offers_quantity"),
        sa.CheckConstraint(
            "status <> 'rejected' OR decision_note IS NOT NULL", name="ck_counter_offers_rejected_has_note"
        ),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE", name="fk_counter_offers_deal_id"),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL", name="fk_counter_offers_created_by_user_id"
        ),
        sa.ForeignKeyConstraint(["decided_by"], ["admin_users.id"], ondelete="SET NULL", name="fk_counter_offers_decided_by"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_counter_offers_deal_time", "counter_offers", ["deal_id", "created_at"])
    op.create_index("ix_counter_offers_status", "counter_offers", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_counter_offers_status", table_name="counter_offers")
    op.drop_index("ix_counter_offers_deal_time", table_name="counter_offers")
    op.drop_table("counter_offers")
