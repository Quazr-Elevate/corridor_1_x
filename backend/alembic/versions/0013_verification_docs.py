"""verification_docs table (KYB file uploads)

Revision ID: 0013_verification_docs
Revises: 0012_signup_personal_first
Create Date: 2026-10-01

Lets users upload business-registration documents (GST cert, incorporation
cert, trade license, etc.) and lets admin review them from the verify queue.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0013_verification_docs"
down_revision: Union[str, None] = "0012_signup_personal_first"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "verification_docs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=300), nullable=False),
        sa.Column("stored_path", sa.String(length=400), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_verification_docs_user_id",
        "verification_docs",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_verification_docs_user_id", table_name="verification_docs")
    op.drop_table("verification_docs")
