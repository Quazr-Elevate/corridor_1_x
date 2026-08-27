"""add photos JSON column to products

Revision ID: 0005_product_photos
Revises: 0004_move_business_email
Create Date: 2026-08-27

Products carry a JSON array of relative photo URLs (e.g. "/uploads/products/xxx.jpg").
Enforcement of "at least one photo" is handled at the API layer so we don't need
a check constraint that varies across dialects.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_product_photos"
down_revision: Union[str, None] = "0004_move_business_email"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.add_column(
            sa.Column("photos", sa.JSON(), nullable=False, server_default="[]")
        )


def downgrade() -> None:
    with op.batch_alter_table("products") as batch:
        batch.drop_column("photos")
