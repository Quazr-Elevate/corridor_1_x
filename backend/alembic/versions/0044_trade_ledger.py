"""The trade ledger and the finance roles

Revision ID: 0044_trade_ledger
Revises: 0043_rank_and_line_currencies
Create Date: 2026-11-28

M5 · S10, CX-111 (A-083); docs/04_data_model.md → "Trade ledger (0044)".

* ``admin_role`` gains ``finance``, ``finance_manager`` and ``logistics``.
* new ``ledger_transactions`` and ``ledger_entries``: double entry, insert
  only (triggers on both databases); on Postgres a deferred constraint
  trigger refuses, at commit, a transaction whose lines don't net to zero
  per currency.

No existing rows change. Reversible, except that Postgres cannot drop an
enum value: after a downgrade ``admin_role`` keeps the three new values, unused.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0044_trade_ledger"
down_revision: Union[str, None] = "0043_rank_and_line_currencies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACCOUNTS = ("bank", "buyer_receivable", "buyer_escrow", "seller_payable", "retention", "corridor_margin",
            "fx_gain_loss", "fees")


def _guards(dialect: str) -> list[str]:
    if dialect == "sqlite":
        return [
            f"CREATE TRIGGER trg_{t}_insert_only_{o.lower()} BEFORE {o} ON {t} "
            "BEGIN SELECT RAISE(ABORT, 'ledger_insert_only'); END"
            for t in ("ledger_transactions", "ledger_entries") for o in ("UPDATE", "DELETE")
        ]
    return [
        "CREATE FUNCTION ledger_insert_only() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
        "RAISE EXCEPTION 'ledger_insert_only' USING ERRCODE = 'integrity_constraint_violation'; END $$",
        *[
            f"CREATE TRIGGER trg_{t}_insert_only BEFORE UPDATE OR DELETE ON {t} "
            "FOR EACH ROW EXECUTE FUNCTION ledger_insert_only()"
            for t in ("ledger_transactions", "ledger_entries")
        ],
        "CREATE FUNCTION ledger_balanced() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
        "IF EXISTS (SELECT 1 FROM ledger_entries WHERE transaction_id = NEW.transaction_id "
        "GROUP BY currency HAVING sum(amount_minor) <> 0) "
        "OR (SELECT count(*) FROM ledger_entries WHERE transaction_id = NEW.transaction_id) < 2 THEN "
        "RAISE EXCEPTION 'ledger_unbalanced' USING ERRCODE = 'integrity_constraint_violation'; END IF; "
        "RETURN NULL; END $$",
        "CREATE CONSTRAINT TRIGGER trg_ledger_entries_balanced AFTER INSERT ON ledger_entries "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION ledger_balanced()",
    ]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # A new enum value can't be used in the transaction that adds it; nothing below uses these.
        with op.get_context().autocommit_block():
            for value in ("finance", "finance_manager", "logistics"):
                op.execute(f"ALTER TYPE admin_role ADD VALUE IF NOT EXISTS '{value}'")
    op.create_table(
        "ledger_transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("memo", sa.String(300), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("reverses_id", sa.Uuid(), nullable=True),
        sa.Column("reference_type", sa.String(30), nullable=True),
        sa.Column("reference_id", sa.String(64), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="RESTRICT", name="fk_ledger_transactions_deal_id"),
        sa.ForeignKeyConstraint(["reverses_id"], ["ledger_transactions.id"], ondelete="RESTRICT",
                                name="fk_ledger_transactions_reverses_id"),
        sa.ForeignKeyConstraint(["created_by"], ["admin_users.id"], ondelete="SET NULL",
                                name="fk_ledger_transactions_created_by"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_ledger_transactions_idempotency"),
        sa.UniqueConstraint("reverses_id", name="uq_ledger_transactions_reverses"),
    )
    op.create_index("ix_ledger_transactions_deal_time", "ledger_transactions", ["deal_id", "created_at"])
    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=True),
        sa.Column("account", sa.String(20), nullable=False),
        sa.Column("leg", sa.String(8), nullable=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"account IN {ACCOUNTS}", name="ck_ledger_entries_account"),
        sa.CheckConstraint("leg IS NULL OR leg IN ('buyer', 'seller', 'corridor')", name="ck_ledger_entries_leg"),
        sa.CheckConstraint("amount_minor <> 0", name="ck_ledger_entries_nonzero"),
        sa.CheckConstraint("length(currency) = 3", name="ck_ledger_entries_currency"),
        sa.ForeignKeyConstraint(["transaction_id"], ["ledger_transactions.id"], ondelete="RESTRICT",
                                name="fk_ledger_entries_transaction_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ledger_entries_transaction", "ledger_entries", ["transaction_id"])
    op.create_index("ix_ledger_entries_deal_account", "ledger_entries", ["deal_id", "account", "currency"])
    for sql in _guards(bind.dialect.name):
        op.execute(sql)


def downgrade() -> None:
    pg = op.get_bind().dialect.name == "postgresql"
    if pg:
        op.execute("DROP TRIGGER IF EXISTS trg_ledger_entries_balanced ON ledger_entries")
        for t in ("ledger_entries", "ledger_transactions"):
            op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_insert_only ON {t}")
        op.execute("DROP FUNCTION IF EXISTS ledger_balanced()")
        op.execute("DROP FUNCTION IF EXISTS ledger_insert_only()")
    else:
        for t in ("ledger_transactions", "ledger_entries"):
            for o in ("update", "delete"):
                op.execute(f"DROP TRIGGER IF EXISTS trg_{t}_insert_only_{o}")
    op.drop_index("ix_ledger_entries_deal_account", table_name="ledger_entries")
    op.drop_index("ix_ledger_entries_transaction", table_name="ledger_entries")
    op.drop_table("ledger_entries")
    op.drop_index("ix_ledger_transactions_deal_time", table_name="ledger_transactions")
    op.drop_table("ledger_transactions")
