"""Desk limits: margin ceiling, exchange-rate age, approval reasons; offer reminder

Revision ID: 0031_desk_limits
Revises: 0030_quotes_offers
Create Date: 2026-11-21

CX-181, CX-182 and CX-183, from the M0–M3 walkthrough review.

* ``trade_settings`` gains two rows, both placeholders until the client sets
  them: ``max_margin_pct`` (25) and ``fx_max_age_days`` (3). A margin above
  the ceiling, or a rate older than the limit, sends a cost sheet to a desk
  manager, as a margin under the floor already does.
* ``cost_sheets`` gains ``max_margin_pct`` (the ceiling in force when the
  sheet was saved; null on older sheets) and ``approval_reasons`` (why the
  sheet waits for a manager; empty on older sheets, whose only reason could
  be the floor, which ``min_margin_pct`` still shows).
* ``offers`` gains ``expiry_reminded_at``: the buyer is reminded once, the
  day before an offer ends. ``uq_offers_cost_sheet_id`` becomes a partial
  unique index over offers that aren't withdrawn, so the desk can withdraw an
  offer and publish a corrected one from the same sheet (CX-186).

Portable (Postgres + SQLite batch ops). Reversible while no sheet has more
than one offer: downgrade restores the plain unique constraint, drops the
columns and the two setting rows.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0031_desk_limits"
down_revision: Union[str, None] = "0030_quotes_offers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Frozen copies of app/modules/rfq/seed.py at this revision.
SETTINGS = (("max_margin_pct", "25", True), ("fx_max_age_days", "3", True))
LIVE = sa.text("status <> 'withdrawn'")


def upgrade() -> None:
    with op.batch_alter_table("cost_sheets") as batch:
        batch.add_column(sa.Column("max_margin_pct", sa.Numeric(6, 2), nullable=True))
        batch.add_column(sa.Column("approval_reasons", sa.JSON(), nullable=False, server_default="[]"))
    with op.batch_alter_table("offers") as batch:
        batch.add_column(sa.Column("expiry_reminded_at", sa.DateTime(timezone=True), nullable=True))
        batch.drop_constraint("uq_offers_cost_sheet_id", type_="unique")
    op.create_index(
        "uq_offers_cost_sheet_live", "offers", ["cost_sheet_id"], unique=True,
        sqlite_where=LIVE, postgresql_where=LIVE,
    )
    settings = sa.table(
        "trade_settings",
        sa.column("key", sa.String),
        sa.column("value", sa.Numeric(12, 4)),
        sa.column("is_placeholder", sa.Boolean),
    )
    op.bulk_insert(settings, [{"key": k, "value": Decimal(v), "is_placeholder": p} for k, v, p in SETTINGS])


def downgrade() -> None:
    op.execute("DELETE FROM trade_settings WHERE key IN ('max_margin_pct', 'fx_max_age_days')")
    op.drop_index("uq_offers_cost_sheet_live", table_name="offers")
    with op.batch_alter_table("offers") as batch:
        batch.create_unique_constraint("uq_offers_cost_sheet_id", ["cost_sheet_id"])
        batch.drop_column("expiry_reminded_at")
    with op.batch_alter_table("cost_sheets") as batch:
        batch.drop_column("approval_reasons")
        batch.drop_column("max_margin_pct")
