"""Bank accounts and bank statements

Revision ID: 0046_banking
Revises: 0045_payment_milestones
Create Date: 2026-11-28

M5 · S10, CX-020, CX-112 (A-083); docs/04_data_model.md → "Bank accounts and statements (0046)".

* new ``bank_accounts`` (encrypted number and holder, keyed hash, last four;
  one live account per business and currency), ``bank_statement_maps``,
  ``bank_statements`` (one per file, by hash) and ``bank_statement_lines``
  (credits, deduplicated by fingerprint; a milestone cleared by one line).
* ``trade_settings`` gains ``payout_cooling_off_hours`` (72, placeholder).

No existing rows change. Reversible.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0046_banking"
down_revision: Union[str, None] = "0045_payment_milestones"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LIVE = sa.text("status IN ('pending', 'verified')")
MATCHED = sa.text("milestone_id IS NOT NULL")


def upgrade() -> None:
    op.create_table(
        "bank_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False),
        sa.Column("country", sa.CHAR(2), nullable=False),
        sa.Column("bank_name", sa.String(100), nullable=False),
        sa.Column("routing_code", sa.String(20), nullable=False),
        sa.Column("account_encrypted", sa.Text(), nullable=False),
        sa.Column("holder_encrypted", sa.Text(), nullable=False),
        sa.Column("key_version", sa.SmallInteger(), nullable=False),
        sa.Column("account_hash", sa.CHAR(64), nullable=False),
        sa.Column("account_last4", sa.String(4), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("verified_by", sa.Uuid(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_note", sa.String(300), nullable=True),
        sa.Column("cooling_off_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_reason", sa.String(300), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'verified', 'rejected', 'retired')", name="ck_bank_accounts_status"),
        sa.CheckConstraint(
            "status <> 'verified' OR (verified_by IS NOT NULL AND verified_at IS NOT NULL AND cooling_off_until IS NOT NULL)",
            name="ck_bank_accounts_verified",
        ),
        sa.CheckConstraint("status <> 'rejected' OR rejected_reason IS NOT NULL", name="ck_bank_accounts_rejected"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE", name="fk_bank_accounts_business_id"),
        sa.ForeignKeyConstraint(["verified_by"], ["admin_users.id"], ondelete="SET NULL", name="fk_bank_accounts_verified_by"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL",
                                name="fk_bank_accounts_created_by_user_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_bank_accounts_live", "bank_accounts", ["business_id", "currency"], unique=True,
                    sqlite_where=LIVE, postgresql_where=LIVE)
    op.create_index("ix_bank_accounts_hash", "bank_accounts", ["account_hash"])
    op.create_index("ix_bank_accounts_status", "bank_accounts", ["status"])
    op.create_table(
        "bank_statement_maps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("columns", sa.JSON(), nullable=False),
        sa.Column("date_format", sa.String(20), nullable=False),
        sa.Column("default_currency", sa.CHAR(3), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["admin_users.id"], ondelete="SET NULL",
                                name="fk_bank_statement_maps_created_by"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_bank_statement_maps_name"),
    )
    op.create_table(
        "bank_statements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("map_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("content_sha256", sa.CHAR(64), nullable=False),
        sa.Column("lines_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lines_new", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lines_matched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("uploaded_by", sa.Uuid(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["map_id"], ["bank_statement_maps.id"], ondelete="RESTRICT", name="fk_bank_statements_map_id"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["admin_users.id"], ondelete="SET NULL", name="fk_bank_statements_uploaded_by"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_sha256", name="uq_bank_statements_content"),
    )
    op.create_table(
        "bank_statement_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("statement_id", sa.Uuid(), nullable=False),
        sa.Column("line_no", sa.Integer(), nullable=False),
        sa.Column("booked_on", sa.Date(), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False),
        sa.Column("reference", sa.String(200), nullable=False),
        sa.Column("payer_account_hash", sa.CHAR(64), nullable=True),
        sa.Column("payer_account_last4", sa.String(4), nullable=True),
        sa.Column("fingerprint", sa.CHAR(64), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("milestone_id", sa.Uuid(), nullable=True),
        sa.Column("match_source", sa.String(6), nullable=True),
        sa.Column("matched_by", sa.Uuid(), nullable=True),
        sa.Column("matched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('unmatched', 'matched', 'ignored')", name="ck_bank_statement_lines_status"),
        sa.CheckConstraint("amount_minor > 0", name="ck_bank_statement_lines_amount"),
        sa.CheckConstraint("(status = 'matched') = (milestone_id IS NOT NULL)", name="ck_bank_statement_lines_matched"),
        sa.CheckConstraint("status <> 'ignored' OR note IS NOT NULL", name="ck_bank_statement_lines_ignored_note"),
        sa.ForeignKeyConstraint(["statement_id"], ["bank_statements.id"], ondelete="RESTRICT",
                                name="fk_bank_statement_lines_statement_id"),
        sa.ForeignKeyConstraint(["milestone_id"], ["payment_milestones.id"], ondelete="RESTRICT",
                                name="fk_bank_statement_lines_milestone_id"),
        sa.ForeignKeyConstraint(["matched_by"], ["admin_users.id"], ondelete="SET NULL",
                                name="fk_bank_statement_lines_matched_by"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint", name="uq_bank_statement_lines_fingerprint"),
    )
    op.create_index("uq_bank_statement_lines_milestone", "bank_statement_lines", ["milestone_id"], unique=True,
                    sqlite_where=MATCHED, postgresql_where=MATCHED)
    op.create_index("ix_bank_statement_lines_status", "bank_statement_lines", ["status", "booked_on"])
    settings = sa.table("trade_settings", sa.column("key", sa.String), sa.column("value", sa.Numeric(12, 4)),
                        sa.column("is_placeholder", sa.Boolean))
    op.bulk_insert(settings, [{"key": "payout_cooling_off_hours", "value": Decimal(72), "is_placeholder": True}])


def downgrade() -> None:
    op.execute("DELETE FROM trade_settings WHERE key = 'payout_cooling_off_hours'")
    op.drop_index("ix_bank_statement_lines_status", table_name="bank_statement_lines")
    op.drop_index("uq_bank_statement_lines_milestone", table_name="bank_statement_lines")
    op.drop_table("bank_statement_lines")
    op.drop_table("bank_statements")
    op.drop_table("bank_statement_maps")
    op.drop_index("ix_bank_accounts_status", table_name="bank_accounts")
    op.drop_index("ix_bank_accounts_hash", table_name="bank_accounts")
    op.drop_index("uq_bank_accounts_live", table_name="bank_accounts")
    op.drop_table("bank_accounts")
