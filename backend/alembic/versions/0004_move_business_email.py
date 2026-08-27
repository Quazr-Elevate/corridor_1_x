"""move business_email from sellers to buyers

Revision ID: 0004_move_business_email
Revises: 0003_business_email
Create Date: 2026-08-27

Business email is really a contact-detail thing (buyer-enquiry inbox), not
a legal-registration thing. It belongs alongside primary email / alt email
on the buyers (unified profile) table.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_move_business_email"
down_revision: Union[str, None] = "0003_business_email"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("buyers") as batch:
        batch.add_column(sa.Column("business_email", sa.String(length=150), nullable=True))

    # Migrate any existing values across, matched by user_id, before dropping.
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE buyers
            SET business_email = (
                SELECT s.business_email FROM sellers s
                WHERE s.user_id = buyers.user_id
                LIMIT 1
            )
            WHERE EXISTS (
                SELECT 1 FROM sellers s
                WHERE s.user_id = buyers.user_id AND s.business_email IS NOT NULL
            )
            """
        )
    )

    with op.batch_alter_table("sellers") as batch:
        batch.drop_column("business_email")


def downgrade() -> None:
    with op.batch_alter_table("sellers") as batch:
        batch.add_column(sa.Column("business_email", sa.String(length=150), nullable=True))
    with op.batch_alter_table("buyers") as batch:
        batch.drop_column("business_email")
