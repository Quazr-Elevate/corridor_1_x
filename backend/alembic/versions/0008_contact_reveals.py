"""add contact_reveals audit table

Revision ID: 0008_contact_reveals
Revises: 0007_consent_and_soft_delete
Create Date: 2026-08-29

One row per (buyer, product) pair — first successful contact reveal.
Idempotent reveals return the same row so a buyer who comes back tomorrow
sees the same contact card without re-triggering the gate.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008_contact_reveals"
down_revision: Union[str, None] = "0007_consent_and_soft_delete"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "contact_reveals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "buyer_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "seller_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.Uuid(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "revealed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("buyer_id", "product_id", name="uq_reveals_buyer_product"),
    )
    op.create_index("ix_reveals_buyer", "contact_reveals", ["buyer_id"])
    op.create_index("ix_reveals_seller", "contact_reveals", ["seller_id"])
    op.create_index("ix_reveals_product", "contact_reveals", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_reveals_product", table_name="contact_reveals")
    op.drop_index("ix_reveals_seller", table_name="contact_reveals")
    op.drop_index("ix_reveals_buyer", table_name="contact_reveals")
    op.drop_table("contact_reveals")
