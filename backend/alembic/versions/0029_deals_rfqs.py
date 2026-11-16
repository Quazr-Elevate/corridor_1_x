"""Deals, RFQs, matches, held countries, trade settings, desk roles

Revision ID: 0029_deals_rfqs
Revises: 0028_credits
Create Date: 2026-11-16

Build plan sections 05 and 20 (CX-089, CX-090, CX-092, CX-093, CX-094);
docs/04_data_model.md → "Deals and RFQs (0029)".

* ``deals`` / ``deal_events`` — the deal and its append-only state trail.
* ``rfqs`` / ``rfq_matches`` — a buyer's request and the sellers proposed
  and confirmed for it.
* ``held_countries`` — countries whose RFQs stop for a compliance look.
  Starts empty: the list is the client's (decision A-039).
* ``trade_settings`` — the desk's numbers. Seeded; the ones the client has
  not set are placeholders (A-037, A-040).
* ``admin_role`` gains ``trade_desk`` and ``desk_manager`` (A-036).

All tables are new, so there is no backfill.
Portable (Postgres + SQLite). Reversible, except that Postgres cannot drop
an enum value: after a downgrade ``admin_role`` keeps the two new values,
unused.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029_deals_rfqs"
down_revision: Union[str, None] = "0028_credits"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEAL_STATUSES = (
    "RFQ_OPEN", "QUOTED", "NEGOTIATING", "LOI_SIGNED", "CONTRACTED", "ADVANCE_PAID", "IN_PRODUCTION", "INSPECTED",
    "SHIPPED", "ARRIVED", "DELIVERED", "ACCEPTED", "SETTLED", "CLOSED", "DISPUTED", "CANCELLED",
)
RFQ_STATUSES = ("draft", "submitted", "held", "matched", "rejected", "unmatched", "expired")
# Placeholders except the last, the same rows as app/modules/rfq/seed.py at this revision.
SETTINGS = (
    ("rfq_open_days", "14", True), ("quote_valid_days", "7", True), ("min_margin_pct", "5", True),
    ("fx_buffer_pct", "2", True), ("freight_max_age_days", "7", False),
)
NOW = sa.func.now()


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(repr(v) for v in values)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable, server_default=None if nullable else NOW)


def _fk(column: str, target: str, name: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([column], [target], name=name, ondelete=ondelete)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # A new enum value cannot be used in the transaction that adds it,
        # and nothing below uses these.
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE admin_role ADD VALUE IF NOT EXISTS 'trade_desk'")
            op.execute("ALTER TYPE admin_role ADD VALUE IF NOT EXISTS 'desk_manager'")

    op.create_table(
        "deals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(12), nullable=False),
        sa.Column("buyer_business_id", sa.Uuid(), nullable=False),
        sa.Column("seller_business_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("cancel_reason", sa.String(200), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id"),
        _fk("buyer_business_id", "businesses.id", "fk_deals_buyer_business_id", "RESTRICT"),
        _fk("seller_business_id", "businesses.id", "fk_deals_seller_business_id", "RESTRICT"),
        sa.UniqueConstraint("code", name="uq_deals_code"),
        sa.CheckConstraint(f"status IN ({_quoted(DEAL_STATUSES)})", name="ck_deals_status"),
        sa.CheckConstraint(
            "seller_business_id IS NULL OR seller_business_id <> buyer_business_id", name="ck_deals_two_parties"
        ),
        sa.CheckConstraint("status <> 'CANCELLED' OR cancel_reason IS NOT NULL", name="ck_deals_cancelled_has_reason"),
    )
    op.create_index("ix_deals_buyer_time", "deals", ["buyer_business_id", sa.text("created_at DESC")])
    op.create_index("ix_deals_status", "deals", ["status"])
    op.create_table(
        "deal_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("actor_type", sa.String(10), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        _ts("created_at"),
        sa.PrimaryKeyConstraint("id"),
        _fk("deal_id", "deals.id", "fk_deal_events_deal_id", "CASCADE"),
        sa.CheckConstraint("actor_type IN ('user', 'admin', 'system')", name="ck_deal_events_actor_type"),
        sa.CheckConstraint("(actor_type = 'system') = (actor_id IS NULL)", name="ck_deal_events_actor_id"),
    )
    op.create_index("ix_deal_events_deal_time", "deal_events", ["deal_id", "created_at"])
    op.create_table(
        "rfqs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=True),
        sa.Column("buyer_business_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="draft"),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("listing_id", sa.Uuid(), nullable=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("product_name", sa.String(200), nullable=False),
        sa.Column("variety", sa.String(100), nullable=True),
        sa.Column("grade", sa.String(100), nullable=True),
        sa.Column("specs", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=True),
        sa.Column("unit", sa.String(10), nullable=False, server_default="MT"),
        sa.Column("packaging", sa.String(50), nullable=True),
        sa.Column("certificate_type_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("target_price_min", sa.BigInteger(), nullable=True),
        sa.Column("target_price_max", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.CHAR(3), nullable=True),
        sa.Column("incoterms", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("payment_terms", sa.String(30), nullable=True),
        sa.Column("delivery_country", sa.CHAR(2), nullable=True),
        sa.Column("destination_port", sa.String(100), nullable=True),
        sa.Column("delivery_from", sa.Date(), nullable=True),
        sa.Column("delivery_to", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        _ts("submitted_at", nullable=True),
        _ts("expires_at", nullable=True),
        sa.Column("desk_reason", sa.String(500), nullable=True),
        _ts("decided_at", nullable=True),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id"),
        _fk("deal_id", "deals.id", "fk_rfqs_deal_id", "RESTRICT"),
        _fk("buyer_business_id", "businesses.id", "fk_rfqs_buyer_business_id", "CASCADE"),
        _fk("created_by_user_id", "users.id", "fk_rfqs_created_by", "SET NULL"),
        _fk("listing_id", "products.id", "fk_rfqs_listing_id", "SET NULL"),
        _fk("decided_by", "admin_users.id", "fk_rfqs_decided_by", "SET NULL"),
        sa.UniqueConstraint("deal_id", name="uq_rfqs_deal_id"),
        sa.CheckConstraint(f"status IN ({_quoted(RFQ_STATUSES)})", name="ck_rfqs_status"),
        sa.CheckConstraint("kind IN ('listing', 'open')", name="ck_rfqs_kind"),
        sa.CheckConstraint("unit IN ('MT', 'kg', 'quintal')", name="ck_rfqs_unit"),
        sa.CheckConstraint("quantity IS NULL OR quantity > 0", name="ck_rfqs_quantity"),
        sa.CheckConstraint(
            "(target_price_min IS NULL OR target_price_min >= 0) AND "
            "(target_price_max IS NULL OR (target_price_min IS NOT NULL AND target_price_max >= target_price_min))",
            name="ck_rfqs_target_price",
        ),
        sa.CheckConstraint(
            "delivery_from IS NULL OR delivery_to IS NULL OR delivery_to >= delivery_from", name="ck_rfqs_window"
        ),
        sa.CheckConstraint(
            "status = 'draft' OR (deal_id IS NOT NULL AND submitted_at IS NOT NULL)", name="ck_rfqs_submitted_has_deal"
        ),
        sa.CheckConstraint("status NOT IN ('rejected', 'held') OR desk_reason IS NOT NULL", name="ck_rfqs_desk_reason"),
    )
    op.create_index("ix_rfqs_buyer_time", "rfqs", ["buyer_business_id", sa.text("created_at DESC")])
    op.create_index("ix_rfqs_queue", "rfqs", ["status", "submitted_at"])
    op.create_table(
        "rfq_matches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rfq_id", sa.Uuid(), nullable=False),
        sa.Column("seller_business_id", sa.Uuid(), nullable=False),
        sa.Column("listing_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="proposed"),
        sa.Column("source", sa.String(5), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        _ts("confirmed_at", nullable=True),
        sa.Column("confirmed_by", sa.Uuid(), nullable=True),
        _ts("viewed_at", nullable=True),
        _ts("created_at"),
        sa.PrimaryKeyConstraint("id"),
        _fk("rfq_id", "rfqs.id", "fk_rfq_matches_rfq_id", "CASCADE"),
        _fk("seller_business_id", "businesses.id", "fk_rfq_matches_seller_business_id", "CASCADE"),
        _fk("listing_id", "products.id", "fk_rfq_matches_listing_id", "SET NULL"),
        _fk("confirmed_by", "admin_users.id", "fk_rfq_matches_confirmed_by", "SET NULL"),
        sa.UniqueConstraint("rfq_id", "seller_business_id", name="uq_rfq_matches_seller"),
        sa.CheckConstraint("status IN ('proposed', 'confirmed', 'removed')", name="ck_rfq_matches_status"),
        sa.CheckConstraint("source IN ('rule', 'desk')", name="ck_rfq_matches_source"),
        sa.CheckConstraint("status <> 'confirmed' OR confirmed_at IS NOT NULL", name="ck_rfq_matches_confirmed_has_date"),
    )
    op.create_index("ix_rfq_matches_seller", "rfq_matches", ["seller_business_id", "status"])
    op.create_table(
        "held_countries",
        sa.Column("code", sa.CHAR(2), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False),
        _ts("created_at"),
        sa.PrimaryKeyConstraint("code"),
        sa.CheckConstraint("length(code) = 2 AND code = upper(code)", name="ck_held_countries_code"),
    )
    settings = op.create_table(
        "trade_settings",
        sa.Column("key", sa.String(40), nullable=False),
        sa.Column("value", sa.Numeric(12, 4), nullable=False),
        sa.Column("is_placeholder", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("key"),
    )
    op.bulk_insert(settings, [{"key": k, "value": Decimal(v), "is_placeholder": p} for k, v, p in SETTINGS])


def downgrade() -> None:
    for table in ("trade_settings", "held_countries", "rfq_matches", "rfqs", "deal_events", "deals"):
        op.drop_table(table)
