"""Plan credits expire with the plan; invoice numbers per financial year

Revision ID: 0034_credit_expiry_invoices
Revises: 0033_country_rules
Create Date: 2026-11-21

CX-171 and CX-173, decisions A-051 and A-065.

* ``credit_wallets.plan_credits``: how much of the balance came from plans.
  Spends use it first; when the plan ends, what is left is written off by an
  ``EXPIRY`` ledger line. Existing wallets start at 0, so nothing already
  bought expires (those credits were sold as non-expiring).
* ``credit_ledger``: ``EXPIRY`` joins the entry types and, like a spend, can
  only take credits.
* ``plan_purchases.invoice_fy`` and the counter table ``invoice_counters``:
  invoice numbers restart at 1 each Indian financial year (C1X/2026-27/0001).
  The unique key becomes (``invoice_fy``, ``invoice_number``); invoices
  already issued are put in the year they were paid, and the counters pick
  up from the highest number used.

Portable (Postgres + SQLite batch ops). Reversible while no two years share
an invoice number and no EXPIRY line exists: downgrade drops the columns,
the table and the new entry type.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence, Union
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from alembic import op

revision: str = "0034_credit_expiry_invoices"
down_revision: Union[str, None] = "0033_country_rules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SPEND = "'RFQ_POST', 'OFFER_UNLOCK', 'RFQ_VIEW', 'LISTING_BOOST', 'AI_QUERY', 'SAMPLE_FEE'"
TOP_UP = "'PLAN_PURCHASE', 'TOP_UP'"
IST = ZoneInfo("Asia/Kolkata")


def _types(with_expiry: bool) -> str:
    extra = ", 'EXPIRY'" if with_expiry else ""
    return f"entry_type IN ({SPEND}, {TOP_UP}, 'ADJUSTMENT', 'REVERSAL'{extra})"


def _sign(with_expiry: bool) -> str:
    takes = f"{SPEND}, 'EXPIRY'" if with_expiry else SPEND
    return f"(NOT entry_type IN ({takes}) OR amount <= 0) AND (NOT entry_type IN ({TOP_UP}) OR amount > 0)"


def _fy(moment) -> str:
    if isinstance(moment, str):
        moment = datetime.fromisoformat(moment)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    local = moment.astimezone(IST)
    start = local.year if local.month >= 4 else local.year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def upgrade() -> None:
    bind = op.get_bind()
    with op.batch_alter_table("credit_wallets") as batch:
        batch.add_column(sa.Column("plan_credits", sa.Integer(), nullable=False, server_default="0"))
        batch.create_check_constraint("ck_credit_wallets_plan_credits", "plan_credits >= 0")
    with op.batch_alter_table("credit_ledger") as batch:
        batch.drop_constraint("ck_credit_ledger_entry_type", type_="check")
        batch.drop_constraint("ck_credit_ledger_sign", type_="check")
        batch.create_check_constraint("ck_credit_ledger_entry_type", _types(True))
        batch.create_check_constraint("ck_credit_ledger_sign", _sign(True))
    op.create_table(
        "invoice_counters",
        sa.Column("fy", sa.String(7), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("fy"),
        sa.CheckConstraint("last_number >= 0", name="ck_invoice_counters_last_number"),
    )
    with op.batch_alter_table("plan_purchases") as batch:
        batch.add_column(sa.Column("invoice_fy", sa.String(7), nullable=True))
        batch.drop_constraint("uq_plan_purchases_invoice_number", type_="unique")
        batch.create_unique_constraint("uq_plan_purchases_invoice", ["invoice_fy", "invoice_number"])

    paid = bind.execute(sa.text("SELECT id, paid_at, invoice_number FROM plan_purchases WHERE invoice_number IS NOT NULL")).all()
    highest: dict[str, int] = {}
    for purchase_id, paid_at, number in paid:
        fy = _fy(paid_at)
        bind.execute(sa.text("UPDATE plan_purchases SET invoice_fy = :fy WHERE id = :id"), {"fy": fy, "id": purchase_id})
        highest[fy] = max(highest.get(fy, 0), number)
    for fy, last in highest.items():
        bind.execute(sa.text("INSERT INTO invoice_counters (fy, last_number) VALUES (:fy, :n)"), {"fy": fy, "n": last})


def downgrade() -> None:
    with op.batch_alter_table("plan_purchases") as batch:
        batch.drop_constraint("uq_plan_purchases_invoice", type_="unique")
        batch.create_unique_constraint("uq_plan_purchases_invoice_number", ["invoice_number"])
        batch.drop_column("invoice_fy")
    op.drop_table("invoice_counters")
    with op.batch_alter_table("credit_ledger") as batch:
        batch.drop_constraint("ck_credit_ledger_sign", type_="check")
        batch.drop_constraint("ck_credit_ledger_entry_type", type_="check")
        batch.create_check_constraint("ck_credit_ledger_entry_type", _types(False))
        batch.create_check_constraint("ck_credit_ledger_sign", _sign(False))
    with op.batch_alter_table("credit_wallets") as batch:
        batch.drop_constraint("ck_credit_wallets_plan_credits", type_="check")
        batch.drop_column("plan_credits")
