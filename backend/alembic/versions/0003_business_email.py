"""add business_email to sellers

Revision ID: 0003_business_email
Revises: 0002_profile_expansion
Create Date: 2026-08-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_business_email"
down_revision: Union[str, None] = "0002_profile_expansion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sellers") as batch:
        batch.add_column(sa.Column("business_email", sa.String(length=150), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sellers") as batch:
        batch.drop_column("business_email")
