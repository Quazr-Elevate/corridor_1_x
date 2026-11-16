"""Quotes, cost sheets, offers and offer unlocks

Revision ID: 0030_quotes_offers
Revises: 0029_deals_rfqs
Create Date: 2026-11-16

Build plan section 06 (CX-095, CX-096, CX-097); docs/04_data_model.md →
"Quotes, cost sheets and offers (0030)".

* ``quotes`` — a matched seller's price and terms for an RFQ.
* ``cost_sheets`` — the desk's costs, the stored FX rate and buffer, the
  margin and the selling price. A CHECK keeps the approver different from
  the author.
* ``offers`` — what the buyer sees: the selling price and terms, never a
  cost or the purchase price.
* ``offer_unlocks`` — who paid to see an offer.

All tables are new, so there is no backfill.
Portable (Postgres + SQLite). Reversible: downgrade drops the tables.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0030_quotes_offers"
down_revision: Union[str, None] = "0029_deals_rfqs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('quotes',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('rfq_id', sa.Uuid(), nullable=False),
    sa.Column('match_id', sa.Uuid(), nullable=False),
    sa.Column('seller_business_id', sa.Uuid(), nullable=False),
    sa.Column('created_by_user_id', sa.Uuid(), nullable=True),
    sa.Column('price_minor', sa.BigInteger(), nullable=False),
    sa.Column('currency', sa.CHAR(length=3), nullable=False),
    sa.Column('quantity', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('unit', sa.String(length=10), nullable=False),
    sa.Column('incoterm', sa.String(length=3), nullable=False),
    sa.Column('port_of_loading', sa.String(length=100), nullable=True),
    sa.Column('lead_time_days', sa.Integer(), nullable=False),
    sa.Column('payment_terms', sa.JSON(), nullable=False),
    sa.Column('valid_until', sa.Date(), nullable=False),
    sa.Column('specs', sa.JSON(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint("unit IN ('MT', 'kg', 'quintal')", name='ck_quotes_unit'),
    sa.CheckConstraint('length(currency) = 3', name='ck_quotes_currency'),
    sa.CheckConstraint('price_minor > 0 AND quantity > 0 AND lead_time_days >= 0', name='ck_quotes_amounts'),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], name='fk_quotes_created_by', ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['match_id'], ['rfq_matches.id'], name='fk_quotes_match_id', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['rfq_id'], ['rfqs.id'], name='fk_quotes_rfq_id', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['seller_business_id'], ['businesses.id'], name='fk_quotes_seller_business_id', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('match_id', name='uq_quotes_match_id')
    )
    op.create_index('ix_quotes_rfq', 'quotes', ['rfq_id'], unique=False)
    op.create_index('ix_quotes_seller_time', 'quotes', ['seller_business_id', sa.text('created_at DESC')], unique=False)
    op.create_table('cost_sheets',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('quote_id', sa.Uuid(), nullable=False),
    sa.Column('deal_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='draft', nullable=False),
    sa.Column('purchase_currency', sa.CHAR(length=3), nullable=False),
    sa.Column('purchase_price_minor', sa.BigInteger(), nullable=False),
    sa.Column('inland_freight_minor', sa.BigInteger(), server_default='0', nullable=False),
    sa.Column('ocean_freight_minor', sa.BigInteger(), server_default='0', nullable=False),
    sa.Column('freight_quoted_on', sa.Date(), nullable=True),
    sa.Column('insurance_minor', sa.BigInteger(), server_default='0', nullable=False),
    sa.Column('inspection_minor', sa.BigInteger(), server_default='0', nullable=False),
    sa.Column('documentation_minor', sa.BigInteger(), server_default='0', nullable=False),
    sa.Column('finance_minor', sa.BigInteger(), server_default='0', nullable=False),
    sa.Column('other_minor', sa.BigInteger(), server_default='0', nullable=False),
    sa.Column('deal_currency', sa.CHAR(length=3), nullable=False),
    sa.Column('fx_rate', sa.Numeric(precision=18, scale=8), nullable=False),
    sa.Column('fx_as_of', sa.Date(), nullable=True),
    sa.Column('fx_buffer_pct', sa.Numeric(precision=6, scale=2), nullable=False),
    sa.Column('margin_pct', sa.Numeric(precision=6, scale=2), nullable=False),
    sa.Column('min_margin_pct', sa.Numeric(precision=6, scale=2), nullable=False),
    sa.Column('sell_price_minor', sa.BigInteger(), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('approved_by', sa.Uuid(), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint("status IN ('draft', 'pending_approval', 'ready', 'published')", name='ck_cost_sheets_status'),
    sa.CheckConstraint('(approved_by IS NULL) = (approved_at IS NULL)', name='ck_cost_sheets_approval_pair'),
    sa.CheckConstraint('approved_by IS NULL OR approved_by <> created_by', name='ck_cost_sheets_second_approver'),
    sa.CheckConstraint('fx_rate > 0 AND fx_buffer_pct >= 0 AND margin_pct >= 0', name='ck_cost_sheets_rates'),
    sa.CheckConstraint('purchase_price_minor > 0 AND sell_price_minor > 0 AND inland_freight_minor >= 0 AND ocean_freight_minor >= 0 AND insurance_minor >= 0 AND inspection_minor >= 0 AND documentation_minor >= 0 AND finance_minor >= 0 AND other_minor >= 0', name='ck_cost_sheets_amounts'),
    sa.ForeignKeyConstraint(['approved_by'], ['admin_users.id'], name='fk_cost_sheets_approved_by', ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['created_by'], ['admin_users.id'], name='fk_cost_sheets_created_by', ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['deal_id'], ['deals.id'], name='fk_cost_sheets_deal_id', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['quote_id'], ['quotes.id'], name='fk_cost_sheets_quote_id', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('quote_id', name='uq_cost_sheets_quote_id')
    )
    op.create_index('ix_cost_sheets_deal', 'cost_sheets', ['deal_id'], unique=False)
    op.create_table('offers',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('deal_id', sa.Uuid(), nullable=False),
    sa.Column('rfq_id', sa.Uuid(), nullable=False),
    sa.Column('quote_id', sa.Uuid(), nullable=False),
    sa.Column('cost_sheet_id', sa.Uuid(), nullable=False),
    sa.Column('buyer_business_id', sa.Uuid(), nullable=False),
    sa.Column('seller_business_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=10), server_default='published', nullable=False),
    sa.Column('price_minor', sa.BigInteger(), nullable=False),
    sa.Column('currency', sa.CHAR(length=3), nullable=False),
    sa.Column('quantity', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('unit', sa.String(length=10), nullable=False),
    sa.Column('incoterm', sa.String(length=3), nullable=False),
    sa.Column('port_of_loading', sa.String(length=100), nullable=True),
    sa.Column('lead_time_days', sa.Integer(), nullable=False),
    sa.Column('payment_terms', sa.JSON(), nullable=False),
    sa.Column('specs_met', sa.Integer(), nullable=False),
    sa.Column('specs_total', sa.Integer(), nullable=False),
    sa.Column('valid_until', sa.Date(), nullable=False),
    sa.Column('published_by', sa.Uuid(), nullable=True),
    sa.Column('published_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint("status IN ('published', 'expired', 'withdrawn')", name='ck_offers_status'),
    sa.CheckConstraint('buyer_business_id <> seller_business_id', name='ck_offers_two_parties'),
    sa.CheckConstraint('price_minor > 0 AND quantity > 0', name='ck_offers_amounts'),
    sa.CheckConstraint('specs_met >= 0 AND specs_met <= specs_total', name='ck_offers_specs'),
    sa.ForeignKeyConstraint(['buyer_business_id'], ['businesses.id'], name='fk_offers_buyer_business_id', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['cost_sheet_id'], ['cost_sheets.id'], name='fk_offers_cost_sheet_id', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['deal_id'], ['deals.id'], name='fk_offers_deal_id', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['published_by'], ['admin_users.id'], name='fk_offers_published_by', ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['quote_id'], ['quotes.id'], name='fk_offers_quote_id', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['rfq_id'], ['rfqs.id'], name='fk_offers_rfq_id', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['seller_business_id'], ['businesses.id'], name='fk_offers_seller_business_id', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('cost_sheet_id', name='uq_offers_cost_sheet_id')
    )
    op.create_index('ix_offers_buyer_time', 'offers', ['buyer_business_id', sa.text('published_at DESC')], unique=False)
    op.create_index('ix_offers_rfq', 'offers', ['rfq_id'], unique=False)
    op.create_table('offer_unlocks',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('offer_id', sa.Uuid(), nullable=False),
    sa.Column('buyer_business_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('unlocked_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['buyer_business_id'], ['businesses.id'], name='fk_offer_unlocks_buyer_business_id', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['offer_id'], ['offers.id'], name='fk_offer_unlocks_offer_id', ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_offer_unlocks_user_id', ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('offer_id', 'buyer_business_id', name='uq_offer_unlocks_offer_buyer')
    )


def downgrade() -> None:
    for table in ("offer_unlocks", "offers", "cost_sheets", "quotes"):
        op.drop_table(table)
