"""Term sheets: versioned, frozen once issued

Revision ID: 0040_term_sheets
Revises: 0039_samples
Create Date: 2026-11-27

M4 · S8, CX-103 (A-076, A-079); docs/04_data_model.md → "Term sheets (0040)".

* new ``term_sheets``: one row per version of a deal's terms, holding both
  sides' prices. ``content_sha256`` is set on issue; the trigger
  ``trg_term_sheets_frozen`` then refuses any change to the terms (on SQLite
  and Postgres alike). Partial unique indexes keep one open and one agreed
  version per deal.

No existing rows change. Reversible: downgrade drops the trigger and the table.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0040_term_sheets"
down_revision: Union[str, None] = "0039_samples"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STATUSES = "('draft', 'issued', 'agreed', 'declined', 'withdrawn', 'superseded')"
# The terms an issued version may never change (TERM_FIELDS in the model, as of this revision).
FROZEN = (
    "product", "quality", "packaging", "quantity", "unit", "incoterm", "port_of_loading", "destination_port",
    "delivery_from", "delivery_to", "buyer_price_minor", "buyer_currency", "buyer_payment_terms",
    "seller_price_minor", "seller_currency", "seller_payment_terms", "margin_pct", "notes", "version",
    "deal_id", "content_sha256",
)


def _freeze_sql(dialect: str) -> list[str]:
    if dialect == "sqlite":
        changed = " OR ".join(f"NEW.{c} IS NOT OLD.{c}" for c in FROZEN)
        return [
            "CREATE TRIGGER trg_term_sheets_frozen BEFORE UPDATE ON term_sheets "
            f"WHEN OLD.content_sha256 IS NOT NULL AND ({changed}) "
            "BEGIN SELECT RAISE(ABORT, 'term_sheet_frozen'); END"
        ]
    changed = " OR ".join(f"NEW.{c} IS DISTINCT FROM OLD.{c}" for c in FROZEN)
    return [
        "CREATE FUNCTION term_sheets_frozen() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
        f"IF OLD.content_sha256 IS NOT NULL AND ({changed}) THEN "
        "RAISE EXCEPTION 'term_sheet_frozen' USING ERRCODE = 'integrity_constraint_violation'; END IF; "
        "RETURN NEW; END $$",
        "CREATE TRIGGER trg_term_sheets_frozen BEFORE UPDATE ON term_sheets "
        "FOR EACH ROW EXECUTE FUNCTION term_sheets_frozen()",
    ]


def upgrade() -> None:
    op.create_table(
        "term_sheets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("product", sa.String(200), nullable=False),
        sa.Column("quality", sa.Text(), nullable=True),
        sa.Column("packaging", sa.String(100), nullable=True),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit", sa.String(10), nullable=False),
        sa.Column("incoterm", sa.String(3), nullable=False),
        sa.Column("port_of_loading", sa.String(100), nullable=True),
        sa.Column("destination_port", sa.String(100), nullable=True),
        sa.Column("delivery_from", sa.Date(), nullable=True),
        sa.Column("delivery_to", sa.Date(), nullable=True),
        sa.Column("buyer_price_minor", sa.BigInteger(), nullable=False),
        sa.Column("buyer_currency", sa.CHAR(3), nullable=False),
        sa.Column("buyer_payment_terms", sa.String(30), nullable=False),
        sa.Column("seller_price_minor", sa.BigInteger(), nullable=False),
        sa.Column("seller_currency", sa.CHAR(3), nullable=False),
        sa.Column("seller_payment_terms", sa.String(30), nullable=False),
        sa.Column("margin_pct", sa.Numeric(6, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("content_sha256", sa.CHAR(64), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("issued_by", sa.Uuid(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("buyer_accepted_by", sa.Uuid(), nullable=True),
        sa.Column("buyer_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seller_accepted_by", sa.Uuid(), nullable=True),
        sa.Column("seller_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("agreed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("declined_side", sa.String(6), nullable=True),
        sa.Column("decline_note", sa.String(500), nullable=True),
        sa.Column("withdraw_note", sa.String(500), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"status IN {STATUSES}", name="ck_term_sheets_status"),
        sa.CheckConstraint("version > 0 AND quantity > 0", name="ck_term_sheets_positive"),
        sa.CheckConstraint("buyer_price_minor > 0 AND seller_price_minor > 0", name="ck_term_sheets_prices"),
        sa.CheckConstraint(
            "delivery_from IS NULL OR delivery_to IS NULL OR delivery_to >= delivery_from",
            name="ck_term_sheets_delivery_window",
        ),
        sa.CheckConstraint("status IN ('draft', 'withdrawn') OR content_sha256 IS NOT NULL", name="ck_term_sheets_hashed_when_issued"),
        sa.CheckConstraint(
            "status NOT IN ('agreed', 'superseded') OR "
            "(buyer_accepted_at IS NOT NULL AND seller_accepted_at IS NOT NULL AND agreed_at IS NOT NULL)",
            name="ck_term_sheets_agreed_by_both",
        ),
        sa.CheckConstraint("status <> 'declined' OR decline_note IS NOT NULL", name="ck_term_sheets_declined_has_note"),
        sa.CheckConstraint("status <> 'withdrawn' OR withdraw_note IS NOT NULL", name="ck_term_sheets_withdrawn_has_note"),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="RESTRICT", name="fk_term_sheets_deal_id"),
        sa.ForeignKeyConstraint(["created_by"], ["admin_users.id"], ondelete="SET NULL", name="fk_term_sheets_created_by"),
        sa.ForeignKeyConstraint(["issued_by"], ["admin_users.id"], ondelete="SET NULL", name="fk_term_sheets_issued_by"),
        sa.ForeignKeyConstraint(
            ["buyer_accepted_by"], ["users.id"], ondelete="SET NULL", name="fk_term_sheets_buyer_accepted_by"
        ),
        sa.ForeignKeyConstraint(
            ["seller_accepted_by"], ["users.id"], ondelete="SET NULL", name="fk_term_sheets_seller_accepted_by"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deal_id", "version", name="uq_term_sheets_deal_version"),
    )
    op.create_index(
        "uq_term_sheets_open", "term_sheets", ["deal_id"], unique=True,
        sqlite_where=sa.text("status IN ('draft', 'issued')"), postgresql_where=sa.text("status IN ('draft', 'issued')"),
    )
    op.create_index(
        "uq_term_sheets_agreed", "term_sheets", ["deal_id"], unique=True,
        sqlite_where=sa.text("status = 'agreed'"), postgresql_where=sa.text("status = 'agreed'"),
    )
    for sql in _freeze_sql(op.get_bind().dialect.name):
        op.execute(sql)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_term_sheets_frozen" + (
        " ON term_sheets" if op.get_bind().dialect.name == "postgresql" else ""
    ))
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS term_sheets_frozen()")
    op.drop_index("uq_term_sheets_agreed", table_name="term_sheets")
    op.drop_index("uq_term_sheets_open", table_name="term_sheets")
    op.drop_table("term_sheets")
