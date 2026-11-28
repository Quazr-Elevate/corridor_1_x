"""The trade ledger (M5 · S10, CX-111, A-083): double entry, append only.

Every movement of trade money is one ``ledger_transactions`` row with two or
more ``ledger_entries`` lines that net to zero in each currency: a debit is
positive, a credit negative, in integer minor units. Nothing is updated or
deleted (triggers refuse it); a correction is a new transaction that
reverses an old one, line for line. This is Corridor One X's books for
trades, separate from the credit wallet (``credit_ledger``)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CHAR,
    DDL,
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    event,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime

#: The chart of accounts. Assets and receivables carry debit balances;
#: payables, escrow held for others and income carry credit balances.
ACCOUNTS = (
    "bank",              # money at the AD bank
    "buyer_receivable",  # what a buyer owes Corridor One X
    "buyer_escrow",      # buyer money held until its release condition
    "seller_payable",    # what Corridor One X owes a seller
    "retention",         # seller money held until acceptance
    "corridor_margin",   # Corridor One X's income on a deal
    "fx_gain_loss",      # the difference conversions leave
    "fees",              # bank and other charges
)
#: Which leg of a deal a line belongs to: the buy leg is Corridor One X and
#: the buyer, the sell leg Corridor One X and the seller.
LEGS = ("buyer", "seller", "corridor")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class LedgerTransaction(Base):
    """One movement of money, made of balancing lines. Insert only."""

    __tablename__ = "ledger_transactions"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_ledger_transactions_idempotency"),
        # A transaction is reversed at most once.
        UniqueConstraint("reverses_id", name="uq_ledger_transactions_reverses"),
        Index("ix_ledger_transactions_deal_time", "deal_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("deals.id", ondelete="RESTRICT", name="fk_ledger_transactions_deal_id"), nullable=True
    )
    #: What happened, e.g. ``buyer_receipt``, ``seller_payout``, ``margin``, ``reversal``.
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    memo: Mapped[str] = mapped_column(String(300), nullable=False)
    #: A retry with the same key finds this transaction instead of posting again.
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    reverses_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("ledger_transactions.id", ondelete="RESTRICT", name="fk_ledger_transactions_reverses_id"),
        nullable=True,
    )
    #: What it came from: ("milestone", id), ("statement_line", id), ("payout", id).
    reference_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("admin_users.id", ondelete="SET NULL", name="fk_ledger_transactions_created_by"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())


class LedgerEntry(Base):
    """One line: an account, a signed amount in minor units, a currency."""

    __tablename__ = "ledger_entries"
    __table_args__ = (
        Index("ix_ledger_entries_transaction", "transaction_id"),
        Index("ix_ledger_entries_deal_account", "deal_id", "account", "currency"),
        CheckConstraint(_in("account", ACCOUNTS), name="ck_ledger_entries_account"),
        CheckConstraint("leg IS NULL OR " + _in("leg", LEGS), name="ck_ledger_entries_leg"),
        CheckConstraint("amount_minor <> 0", name="ck_ledger_entries_nonzero"),
        CheckConstraint("length(currency) = 3", name="ck_ledger_entries_currency"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ledger_transactions.id", ondelete="RESTRICT", name="fk_ledger_entries_transaction_id"),
        nullable=False,
    )
    #: Copied from the transaction so a deal's lines are read without a join.
    deal_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    account: Mapped[str] = mapped_column(String(20), nullable=False)
    leg: Mapped[str | None] = mapped_column(String(8), nullable=True)
    #: Debit positive, credit negative.
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())


def ledger_guard_sql(dialect: str) -> list[str]:
    """Insert-only triggers on both tables, and on Postgres a deferred check
    that each transaction's lines net to zero per currency at commit. For
    schemas built from the models (tests); migration 0044 has its own copy."""
    if dialect == "sqlite":
        return [
            f"CREATE TRIGGER trg_{t}_insert_only_{op.lower()} BEFORE {op} ON {t} "
            "BEGIN SELECT RAISE(ABORT, 'ledger_insert_only'); END"
            for t in ("ledger_transactions", "ledger_entries") for op in ("UPDATE", "DELETE")
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


def _table_for(sql: str):
    # ledger_transactions is created first, so the shared function goes with it.
    if "ON ledger_transactions" in sql or "CREATE FUNCTION ledger_insert_only" in sql:
        return LedgerTransaction.__table__
    return LedgerEntry.__table__


for _dialect in ("sqlite", "postgresql"):
    for _sql in ledger_guard_sql(_dialect):
        event.listen(_table_for(_sql), "after_create", DDL(_sql).execute_if(dialect=_dialect))
