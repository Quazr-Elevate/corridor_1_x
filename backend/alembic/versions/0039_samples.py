"""Samples: chain of custody through the hub

Revision ID: 0039_samples
Revises: 0038_counter_offers
Create Date: 2026-11-26

M4 · S8, CX-102 (A-077); docs/04_data_model.md → "Samples (0039)".

* new ``samples``: one sample on a deal, its status along seller → hub →
  split and seal → forwarded → buyer → reviewed, the seal numbers and
  courier references, and the buyer's verdict. A check makes forwarding
  impossible without both seal numbers.
* new ``sample_events``: every hop with its time and who recorded it.

No existing rows change. Portable. Reversible: downgrade drops both tables.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0039_samples"
down_revision: Union[str, None] = "0038_counter_offers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STATUSES = "('requested', 'seller_dispatched', 'at_hub', 'split_sealed', 'forwarded', 'buyer_received', 'reviewed')"


def upgrade() -> None:
    op.create_table(
        "samples",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("seller_courier_ref", sa.String(100), nullable=True),
        sa.Column("retained_seal_no", sa.String(40), nullable=True),
        sa.Column("forward_seal_no", sa.String(40), nullable=True),
        sa.Column("forward_courier_ref", sa.String(100), nullable=True),
        sa.Column("verdict", sa.String(6), nullable=True),
        sa.Column("review_note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"status IN {STATUSES}", name="ck_samples_status"),
        sa.CheckConstraint("verdict IS NULL OR verdict IN ('passed', 'failed')", name="ck_samples_verdict"),
        sa.CheckConstraint(
            "status NOT IN ('split_sealed', 'forwarded', 'buyer_received', 'reviewed') "
            "OR (retained_seal_no IS NOT NULL AND forward_seal_no IS NOT NULL)",
            name="ck_samples_sealed_before_forward",
        ),
        sa.CheckConstraint("(status = 'reviewed') = (verdict IS NOT NULL)", name="ck_samples_reviewed_has_verdict"),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE", name="fk_samples_deal_id"),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"], ["users.id"], ondelete="SET NULL", name="fk_samples_requested_by_user_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_samples_deal", "samples", ["deal_id"])
    op.create_index("ix_samples_status", "samples", ["status"])
    op.create_table(
        "sample_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sample_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.String(20), nullable=True),
        sa.Column("to_status", sa.String(20), nullable=False),
        sa.Column("actor_type", sa.String(5), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("actor_type IN ('user', 'admin')", name="ck_sample_events_actor_type"),
        sa.ForeignKeyConstraint(["sample_id"], ["samples.id"], ondelete="CASCADE", name="fk_sample_events_sample_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sample_events_sample_time", "sample_events", ["sample_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_sample_events_sample_time", table_name="sample_events")
    op.drop_table("sample_events")
    op.drop_index("ix_samples_status", table_name="samples")
    op.drop_index("ix_samples_deal", table_name="samples")
    op.drop_table("samples")
