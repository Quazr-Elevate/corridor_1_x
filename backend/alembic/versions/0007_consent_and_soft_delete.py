"""add consent tracking + soft-delete columns

Revision ID: 0007_consent_and_soft_delete
Revises: 0006_merge_profiles
Create Date: 2026-08-29

Compliance additions (DPDP Act + UAE PDPL):
- profiles.consent_at         — when the user checked the T&C box at signup
- profiles.consent_version    — versioned "T-2026-08-29" so we can prove which
                                policy they agreed to if it changes later
- users.deleted_at            — soft-delete flag for right-to-erasure
                                (hard delete via cron/cleanup job later)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_consent_and_soft_delete"
down_revision: Union[str, None] = "0006_merge_profiles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("profiles") as batch:
        batch.add_column(
            sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column("consent_version", sa.String(length=30), nullable=True)
        )
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("deleted_at")
    with op.batch_alter_table("profiles") as batch:
        batch.drop_column("consent_version")
        batch.drop_column("consent_at")
