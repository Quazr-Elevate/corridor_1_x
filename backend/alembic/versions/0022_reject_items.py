"""per-item rejection: businesses.verification_rejected_items

Revision ID: 0022_reject_items
Revises: 0021_kyb_profile
Create Date: 2026-10-31

Implements docs/04_data_model.md → "Combined KYB review (0022)": the admin
ticks which items failed when rejecting a business — profile fields
(``addressLine``) and KYB entries (``kyb:<code>`` / ``doc:<entry id>``).
JSON list, nullable; cleared on resubmit and approval.

Portable (Postgres + SQLite batch ops). Reversible.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022_reject_items"
down_revision: Union[str, None] = "0021_kyb_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("businesses") as batch:
        batch.add_column(sa.Column("verification_rejected_items", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("businesses") as batch:
        batch.drop_column("verification_rejected_items")
