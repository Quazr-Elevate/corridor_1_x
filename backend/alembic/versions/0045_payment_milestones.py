"""Payment milestones, the outlay cap and the retention

Revision ID: 0045_payment_milestones
Revises: 0044_trade_ledger
Create Date: 2026-11-28

M5 · S10, CX-110 (A-083); docs/04_data_model.md → "Payment milestones (0045)".

* new ``payment_milestones``: each leg's payments, generated when a deal's
  contracts take effect.
* ``trade_settings`` gains ``outlay_cap_months`` (4) and ``retention_pct``
  (10), both placeholders: the cap until the AD bank answers CX-078, the
  retention until the client confirms it.

No existing rows change. Reversible.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0045_payment_milestones"
down_revision: Union[str, None] = "0044_trade_ledger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

KINDS = "('advance', 'balance', 'cad', 'lc_payment', 'da_payment', 'open_account', 'escrow_funding', 'retention')"
EVENTS = "('contract_effective', 'shipment', 'documents', 'acceptance')"
GATES = "('start_production', 'ship', 'release_documents', 'pay_seller', 'release_retention')"


def upgrade() -> None:
    op.create_table(
        "payment_milestones",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=False),
        sa.Column("contract_id", sa.Uuid(), nullable=False),
        sa.Column("leg", sa.String(6), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False),
        sa.Column("due_event", sa.String(20), nullable=False),
        sa.Column("due_days", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gate", sa.String(20), nullable=False),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("leg IN ('buyer', 'seller')", name="ck_payment_milestones_leg"),
        sa.CheckConstraint(f"kind IN {KINDS}", name="ck_payment_milestones_kind"),
        sa.CheckConstraint(f"due_event IN {EVENTS}", name="ck_payment_milestones_due_event"),
        sa.CheckConstraint(f"gate IN {GATES}", name="ck_payment_milestones_gate"),
        sa.CheckConstraint("status IN ('open', 'cleared', 'paid', 'void')", name="ck_payment_milestones_status"),
        sa.CheckConstraint("amount_minor > 0 AND due_days >= 0 AND sequence > 0", name="ck_payment_milestones_amounts"),
        sa.CheckConstraint(
            "(status <> 'cleared' OR leg = 'buyer') AND (status <> 'paid' OR leg = 'seller')",
            name="ck_payment_milestones_status_leg",
        ),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="RESTRICT", name="fk_payment_milestones_deal_id"),
        sa.ForeignKeyConstraint(["contract_id"], ["deal_documents.id"], ondelete="RESTRICT",
                                name="fk_payment_milestones_contract_id"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deal_id", "leg", "sequence", name="uq_payment_milestones_deal_leg_sequence"),
    )
    op.create_index("ix_payment_milestones_status", "payment_milestones", ["status", "leg"])
    settings = sa.table("trade_settings", sa.column("key", sa.String), sa.column("value", sa.Numeric(12, 4)),
                        sa.column("is_placeholder", sa.Boolean))
    op.bulk_insert(settings, [
        {"key": "outlay_cap_months", "value": Decimal(4), "is_placeholder": True},
        {"key": "retention_pct", "value": Decimal(10), "is_placeholder": True},
    ])


def downgrade() -> None:
    op.execute("DELETE FROM trade_settings WHERE key IN ('outlay_cap_months', 'retention_pct')")
    op.drop_index("ix_payment_milestones_status", table_name="payment_milestones")
    op.drop_table("payment_milestones")
