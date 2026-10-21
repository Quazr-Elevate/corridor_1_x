"""exchange rates: exchange_rates, products.price_usd, users.display_currency

Revision ID: 0020_exchange_rates
Revises: 0019_business_entity
Create Date: 2026-10-17

Implements docs/04_data_model.md → "Exchange rates (multi-currency prices)":

* new table ``exchange_rates`` (USD-based daily rates) with
  ``uq_exchange_rates_quote_day``, ``ix_exchange_rates_latest``,
  ``ck_exchange_rates_rate_positive``, ``ck_exchange_rates_codes``;
* ``products.price_usd`` numeric(14,2) + ``price_usd_as_of`` date,
  ``ix_products_market_price`` (category, price_usd) on live rows,
  ``ck_products_price_usd``;
* ``users.display_currency`` char(3) NOT NULL, backfilled from the business
  country (IN → INR, AE → AED, else USD), ``ck_users_display_currency``.

Bootstrap rates (so ``price_usd`` can be filled for existing listings right
away; the first real fetch replaces them): 1 USD = 95 INR (``manual``) and
1 USD = 3.6725 AED (``pegged``), dated the migration day. They are inserted
in offline (``--sql``) mode too; the price_usd / display_currency backfills
are Python data steps and only run online.

Portable (Postgres + SQLite batch ops). Reversible: downgrade drops it all.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020_exchange_rates"
down_revision: Union[str, None] = "0019_business_entity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

log = logging.getLogger("alembic.runtime.migration")

# Frozen copies (migrations must not import app code).
SUPPORTED = ("INR", "AED", "USD")
COUNTRY_CURRENCY = {"IN": "INR", "AE": "AED"}
BOOTSTRAP_RATES = (("INR", Decimal("95"), "manual"), ("AED", Decimal("3.6725"), "pegged"))
_LIVE = {"sqlite_where": sa.text("deleted_at IS NULL"), "postgresql_where": sa.text("deleted_at IS NULL")}
_CENT = Decimal("0.01")

_products = sa.table(
    "products",
    sa.column("id", sa.Uuid()),
    sa.column("currency", sa.CHAR(3)),
    sa.column("price_per_unit", sa.Numeric(12, 2)),
    sa.column("price_usd", sa.Numeric(14, 2)),
    sa.column("price_usd_as_of", sa.Date()),
    sa.column("deleted_at", sa.DateTime(timezone=True)),
)
_users = sa.table("users", sa.column("id", sa.Uuid()), sa.column("business_id", sa.Uuid()),
                  sa.column("display_currency", sa.CHAR(3)))
_businesses = sa.table("businesses", sa.column("id", sa.Uuid()), sa.column("country", sa.CHAR(2)))


def upgrade() -> None:
    ctx = op.get_context()
    online = not ctx.as_sql
    today = datetime.now(tz=timezone.utc).date()

    # 1. exchange_rates ─────────────────────────────────────────────────
    rates = op.create_table(
        "exchange_rates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("base", sa.CHAR(3), nullable=False),
        sa.Column("quote", sa.CHAR(3), nullable=False),
        sa.Column("rate", sa.Numeric(18, 8), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("base", "quote", "as_of", name="uq_exchange_rates_quote_day"),
        sa.CheckConstraint("rate > 0", name="ck_exchange_rates_rate_positive"),
        sa.CheckConstraint("length(base) = 3 AND length(quote) = 3", name="ck_exchange_rates_codes"),
    )
    op.create_index("ix_exchange_rates_latest", "exchange_rates", ["quote", sa.text("as_of DESC")])
    op.bulk_insert(
        rates,
        [
            {"id": uuid.uuid4(), "base": "USD", "quote": q, "rate": r, "as_of": today, "source": src,
             "fetched_at": datetime.now(tz=timezone.utc)}
            for q, r, src in BOOTSTRAP_RATES
        ],
    )

    # 2. products.price_usd ─────────────────────────────────────────────
    with op.batch_alter_table("products") as batch:
        batch.add_column(sa.Column("price_usd", sa.Numeric(14, 2), nullable=True))
        batch.add_column(sa.Column("price_usd_as_of", sa.Date(), nullable=True))
        batch.create_check_constraint("ck_products_price_usd", "price_usd IS NULL OR price_usd >= 0")
    op.create_index("ix_products_market_price", "products", ["category", "price_usd"], **_LIVE)

    # 3. users.display_currency ─────────────────────────────────────────
    allowed = ", ".join(f"'{c}'" for c in SUPPORTED)
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("display_currency", sa.CHAR(3), nullable=False, server_default="USD"))
        batch.create_check_constraint("ck_users_display_currency", f"display_currency IN ({allowed})")

    if online:
        bind = op.get_bind()
        _backfill_price_usd(bind, today)
        _backfill_display_currency(bind)


def _backfill_price_usd(bind, today) -> None:
    rate_of = {q: r for q, r, _ in BOOTSTRAP_RATES} | {"USD": Decimal(1)}
    rows = bind.execute(
        sa.select(_products.c.id, _products.c.currency, _products.c.price_per_unit).where(
            _products.c.deleted_at.is_(None), _products.c.price_per_unit.is_not(None)
        )
    ).all()
    done = skipped = 0
    for r in rows:
        rate = rate_of.get((r.currency or "").upper())
        if rate is None:
            skipped += 1
            continue
        usd = (Decimal(str(r.price_per_unit)) / rate).quantize(_CENT, rounding=ROUND_HALF_UP)
        bind.execute(
            sa.update(_products).where(_products.c.id == r.id).values(price_usd=usd, price_usd_as_of=today)
        )
        done += 1
    log.info("0020: price_usd filled for %d listing(s)", done)
    if skipped:
        log.warning("0020: %d listing(s) in an unsupported currency left without price_usd", skipped)


def _backfill_display_currency(bind) -> None:
    rows = bind.execute(
        sa.select(_users.c.id, _businesses.c.country).select_from(
            _users.outerjoin(_businesses, _businesses.c.id == _users.c.business_id)
        )
    ).all()
    counts: dict[str, int] = {}
    for r in rows:
        cur = COUNTRY_CURRENCY.get((r.country or "").strip().upper(), "USD")
        counts[cur] = counts.get(cur, 0) + 1
        if cur != "USD":  # USD is the column default
            bind.execute(sa.update(_users).where(_users.c.id == r.id).values(display_currency=cur))
    log.info("0020: display_currency backfilled %s", dict(sorted(counts.items())))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("ck_users_display_currency", type_="check")
        batch.drop_column("display_currency")
    op.drop_index("ix_products_market_price", table_name="products")
    with op.batch_alter_table("products") as batch:
        batch.drop_constraint("ck_products_price_usd", type_="check")
        batch.drop_column("price_usd_as_of")
        batch.drop_column("price_usd")
    op.drop_index("ix_exchange_rates_latest", table_name="exchange_rates")
    op.drop_table("exchange_rates")
