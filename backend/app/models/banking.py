"""Bank accounts and bank statements (M5 · S10, CX-020, CX-112, A-083).

A business's bank account is encrypted like a KYB number (``core/crypto``):
the number and the holder's name as AES-GCM ciphertext, a keyed hash so an
incoming payment can be matched to its payer without decrypting, and the
last four digits for display. Finance verifies an account; a payout to it
waits out a cooling-off period, and a new account starts both again.

Money moves at the AD bank, not here (A-083): finance uploads the bank's
CSV statement, read through a saved column map, and each credit line is
matched to a buyer's payment milestone or left in a queue for a person."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CHAR,
    JSON,
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime

ACCOUNT_STATUSES = ("pending", "verified", "rejected", "retired")
LINE_STATUSES = ("unmatched", "matched", "ignored")


class BankAccount(Base):
    """One business's account for one currency. At most one live (pending or
    verified) per business and currency; a new one retires the old."""

    __tablename__ = "bank_accounts"
    __table_args__ = (
        Index(
            "uq_bank_accounts_live", "business_id", "currency", unique=True,
            sqlite_where=text("status IN ('pending', 'verified')"),
            postgresql_where=text("status IN ('pending', 'verified')"),
        ),
        Index("ix_bank_accounts_hash", "account_hash"),
        Index("ix_bank_accounts_status", "status"),
        CheckConstraint("status IN ('pending', 'verified', 'rejected', 'retired')", name="ck_bank_accounts_status"),
        CheckConstraint(
            "status <> 'verified' OR (verified_by IS NOT NULL AND verified_at IS NOT NULL AND cooling_off_until IS NOT NULL)",
            name="ck_bank_accounts_verified",
        ),
        CheckConstraint("status <> 'rejected' OR rejected_reason IS NOT NULL", name="ck_bank_accounts_rejected"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE", name="fk_bank_accounts_business_id"), nullable=False
    )
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    country: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(100), nullable=False)
    #: IFSC in India, SWIFT/BIC elsewhere: names the bank, not the holder.
    routing_code: Mapped[str] = mapped_column(String(20), nullable=False)
    account_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    holder_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    key_version: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    #: Keyed hash of the normalised number (scope ``bank_account``).
    account_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    account_last4: Mapped[str] = mapped_column(String(4), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("admin_users.id", ondelete="SET NULL", name="fk_bank_accounts_verified_by"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    #: How it was checked (a penny drop, a bank letter), for the audit trail.
    verification_note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    #: No payout to this account before this time (CX-121).
    cooling_off_until: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    rejected_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL", name="fk_bank_accounts_created_by_user_id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    retired_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class BankStatementMap(Base):
    """How one bank's CSV export reads: which column holds what."""

    __tablename__ = "bank_statement_maps"
    __table_args__ = (UniqueConstraint("name", name="uq_bank_statement_maps_name"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    #: Header names: {"date", "amount", "reference", "payer_account", "currency"?}.
    columns: Mapped[dict] = mapped_column(JSON, nullable=False)
    #: ``strftime`` pattern of the date column, e.g. ``%d/%m/%Y``.
    date_format: Mapped[str] = mapped_column(String(20), nullable=False)
    #: When the file has no currency column.
    default_currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("admin_users.id", ondelete="SET NULL", name="fk_bank_statement_maps_created_by"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())


class BankStatement(Base):
    """One uploaded file. The same file twice is refused by its hash."""

    __tablename__ = "bank_statements"
    __table_args__ = (UniqueConstraint("content_sha256", name="uq_bank_statements_content"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    map_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("bank_statement_maps.id", ondelete="RESTRICT", name="fk_bank_statements_map_id"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(200), nullable=False)
    content_sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    lines_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lines_new: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lines_matched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("admin_users.id", ondelete="SET NULL", name="fk_bank_statements_uploaded_by"), nullable=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())


class BankStatementLine(Base):
    """One credit on a statement. Lines seen in an earlier statement (same
    date, amount, currency, reference and payer) are kept once."""

    __tablename__ = "bank_statement_lines"
    __table_args__ = (
        UniqueConstraint("fingerprint", name="uq_bank_statement_lines_fingerprint"),
        # A milestone is cleared by one line only.
        Index(
            "uq_bank_statement_lines_milestone", "milestone_id", unique=True,
            sqlite_where=text("milestone_id IS NOT NULL"), postgresql_where=text("milestone_id IS NOT NULL"),
        ),
        Index("ix_bank_statement_lines_status", "status", "booked_on"),
        CheckConstraint("status IN ('unmatched', 'matched', 'ignored')", name="ck_bank_statement_lines_status"),
        CheckConstraint("amount_minor > 0", name="ck_bank_statement_lines_amount"),
        CheckConstraint("(status = 'matched') = (milestone_id IS NOT NULL)", name="ck_bank_statement_lines_matched"),
        CheckConstraint("status <> 'ignored' OR note IS NOT NULL", name="ck_bank_statement_lines_ignored_note"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    statement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("bank_statements.id", ondelete="RESTRICT", name="fk_bank_statement_lines_statement_id"),
        nullable=False,
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    booked_on: Mapped[date] = mapped_column(Date, nullable=False)
    amount_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False)
    reference: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    #: The payer's account as a keyed hash (same scope as ``bank_accounts``), and its last four.
    payer_account_hash: Mapped[str | None] = mapped_column(CHAR(64), nullable=True)
    payer_account_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    fingerprint: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="unmatched")
    milestone_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("payment_milestones.id", ondelete="RESTRICT", name="fk_bank_statement_lines_milestone_id"),
        nullable=True,
    )
    match_source: Mapped[str | None] = mapped_column(String(6), nullable=True)
    matched_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("admin_users.id", ondelete="SET NULL", name="fk_bank_statement_lines_matched_by"), nullable=True
    )
    matched_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
