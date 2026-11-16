"""Credit wallet, ledger, free quota, prices, plans and purchases

Revision ID: 0028_credits
Revises: 0027_identity_vault
Create Date: 2026-11-16

Build plan section 17 (CX-084, CX-085); docs/04_data_model.md → "Credits
(0028)".

* ``credit_wallets`` — one row per company, ``balance >= 0``.
* ``credit_ledger`` — append-only lines; UNIQUE (business, idempotency key).
* ``credit_free_quotas`` — free uses keyed on the registration number's hash.
* ``credit_prices`` / ``credit_plans`` — admin-edited configuration.
* ``plan_purchases`` / ``payment_events`` — checkouts and webhook deliveries.
* ``idempotency_keys`` — stored answers for requests that must not run twice.

All tables are new, so there is no backfill; a wallet is created the first
time a company's wallet is read. Seeds placeholder prices and plans
(decision A-031): the client has not set the real ones.
Portable (Postgres + SQLite). Reversible: downgrade drops the tables and
with them every balance and ledger line.
"""
from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0028_credits"
down_revision: Union[str, None] = "0027_identity_vault"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SPEND = "'RFQ_POST', 'OFFER_UNLOCK', 'RFQ_VIEW', 'LISTING_BOOST', 'AI_QUERY', 'SAMPLE_FEE'"
TOP_UP = "'PLAN_PURCHASE', 'TOP_UP'"
NOW = sa.func.now()

# Placeholders, the same rows as app/modules/credits/seed.py at this revision.
PRICES = (("RFQ_POST", 5), ("OFFER_UNLOCK", 2), ("RFQ_VIEW", 1), ("LISTING_BOOST", 10), ("AI_QUERY", 1), ("SAMPLE_FEE", 5))
PLANS = (
    ("starter", "Starter", "plan", 50, 99900, "INR", 30),
    ("growth", "Growth", "plan", 200, 349900, "INR", 30),
    ("topup-25", "25 credits", "top_up", 25, 59900, "INR", None),
)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable, server_default=None if nullable else NOW)


def _fk(column: str, target: str, name: str, ondelete: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint([column], [target], name=name, ondelete=ondelete)


def upgrade() -> None:
    op.create_table(
        "credit_wallets",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("balance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("plan_code", sa.String(40), nullable=True),
        _ts("plan_expires_at", nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("business_id"),
        _fk("business_id", "businesses.id", "fk_credit_wallets_business_id", "CASCADE"),
        sa.CheckConstraint("balance >= 0", name="ck_credit_wallets_balance"),
    )
    op.create_table(
        "credit_ledger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("entry_type", sa.String(20), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("free", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("reference_type", sa.String(30), nullable=True),
        sa.Column("reference_id", sa.String(64), nullable=True),
        sa.Column("idempotency_key", sa.String(100), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("note", sa.String(200), nullable=True),
        _ts("created_at"),
        sa.PrimaryKeyConstraint("id"),
        _fk("business_id", "businesses.id", "fk_credit_ledger_business_id", "CASCADE"),
        _fk("created_by_user_id", "users.id", "fk_credit_ledger_created_by", "SET NULL"),
        sa.UniqueConstraint("business_id", "idempotency_key", name="uq_credit_ledger_idempotency"),
        sa.CheckConstraint(
            f"entry_type IN ({SPEND}, {TOP_UP}, 'ADJUSTMENT', 'REVERSAL')", name="ck_credit_ledger_entry_type"
        ),
        sa.CheckConstraint(
            f"(NOT entry_type IN ({SPEND}) OR amount <= 0) AND (NOT entry_type IN ({TOP_UP}) OR amount > 0)",
            name="ck_credit_ledger_sign",
        ),
        sa.CheckConstraint("balance_after >= 0", name="ck_credit_ledger_balance_after"),
    )
    op.create_index("ix_credit_ledger_business_time", "credit_ledger", ["business_id", sa.text("created_at DESC")])
    op.create_table(
        "credit_free_quotas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("registration_hash", sa.String(64), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=True),
        sa.Column("allowance", sa.Integer(), nullable=False),
        sa.Column("used", sa.Integer(), nullable=False, server_default="0"),
        _ts("created_at"),
        sa.PrimaryKeyConstraint("id"),
        _fk("business_id", "businesses.id", "fk_credit_free_quotas_business_id", "SET NULL"),
        sa.UniqueConstraint("action", "registration_hash", name="uq_credit_free_quotas_registration"),
        sa.CheckConstraint("used >= 0 AND used <= allowance", name="ck_credit_free_quotas_used"),
        sa.CheckConstraint(f"action IN ({SPEND})", name="ck_credit_free_quotas_action"),
    )
    prices = op.create_table(
        "credit_prices",
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("is_placeholder", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("action"),
        sa.CheckConstraint("credits >= 0", name="ck_credit_prices_credits"),
        sa.CheckConstraint(f"action IN ({SPEND})", name="ck_credit_prices_action"),
    )
    plans = op.create_table(
        "credit_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("price_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False),
        sa.Column("period_days", sa.Integer(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_placeholder", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        _ts("updated_at"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_credit_plans_code"),
        sa.CheckConstraint("kind IN ('plan', 'top_up')", name="ck_credit_plans_kind"),
        sa.CheckConstraint("credits > 0 AND price_minor >= 0", name="ck_credit_plans_amounts"),
        sa.CheckConstraint("length(currency) = 3", name="ck_credit_plans_currency"),
        sa.CheckConstraint(
            "(kind = 'plan' AND period_days > 0) OR (kind = 'top_up' AND period_days IS NULL)",
            name="ck_credit_plans_period",
        ),
    )
    op.create_table(
        "plan_purchases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=True),
        sa.Column("plan_code", sa.String(40), nullable=False),
        sa.Column("plan_kind", sa.String(10), nullable=False),
        sa.Column("period_days", sa.Integer(), nullable=True),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="created"),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_order_id", sa.String(80), nullable=False),
        sa.Column("provider_payment_id", sa.String(80), nullable=True),
        sa.Column("invoice_number", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        _ts("created_at"),
        _ts("paid_at", nullable=True),
        sa.PrimaryKeyConstraint("id"),
        _fk("business_id", "businesses.id", "fk_plan_purchases_business_id", "CASCADE"),
        _fk("plan_id", "credit_plans.id", "fk_plan_purchases_plan_id", "SET NULL"),
        _fk("created_by_user_id", "users.id", "fk_plan_purchases_created_by", "SET NULL"),
        sa.UniqueConstraint("provider", "provider_order_id", name="uq_plan_purchases_order"),
        sa.UniqueConstraint("invoice_number", name="uq_plan_purchases_invoice_number"),
        sa.CheckConstraint("status IN ('created', 'paid', 'failed')", name="ck_plan_purchases_status"),
        sa.CheckConstraint("status <> 'paid' OR paid_at IS NOT NULL", name="ck_plan_purchases_paid_has_date"),
    )
    op.create_index("ix_plan_purchases_business_time", "plan_purchases", ["business_id", sa.text("created_at DESC")])
    op.create_table(
        "payment_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("event_id", sa.String(120), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("purchase_id", sa.Uuid(), nullable=True),
        sa.Column("outcome", sa.String(20), nullable=False),
        _ts("received_at"),
        sa.PrimaryKeyConstraint("id"),
        _fk("purchase_id", "plan_purchases.id", "fk_payment_events_purchase_id", "SET NULL"),
        sa.UniqueConstraint("provider", "event_id", name="uq_payment_events_event"),
    )
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("route", sa.String(80), nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("request_hash", sa.CHAR(64), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        _ts("created_at"),
        sa.PrimaryKeyConstraint("id"),
        _fk("business_id", "businesses.id", "fk_idempotency_keys_business_id", "CASCADE"),
        sa.UniqueConstraint("business_id", "route", "key", name="uq_idempotency_keys_key"),
    )
    op.bulk_insert(prices, [{"action": a, "credits": c, "is_placeholder": True} for a, c in PRICES])
    op.bulk_insert(
        plans,
        [
            {
                "id": uuid.uuid4(), "code": code, "name": name, "kind": kind, "credits": credits,
                "price_minor": price, "currency": currency, "period_days": period, "active": True,
                "is_placeholder": True, "sort_order": i,
            }
            for i, (code, name, kind, credits, price, currency, period) in enumerate(PLANS)
        ],
    )


def downgrade() -> None:
    for table in (
        "idempotency_keys", "payment_events", "plan_purchases", "credit_plans", "credit_prices",
        "credit_free_quotas", "credit_ledger", "credit_wallets",
    ):
        op.drop_table(table)
