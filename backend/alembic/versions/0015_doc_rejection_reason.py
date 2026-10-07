"""verification_docs: rejection_reason

Revision ID: 0015_doc_rejection_reason
Revises: 0014_doc_cert_type_status
Create Date: 2026-10-05

Admin captures a short note when rejecting a document; it's shown back to
the user on login so they know what to fix on the re-upload.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0015_doc_rejection_reason"
down_revision: Union[str, None] = "0014_doc_cert_type_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "verification_docs",
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("verification_docs", "rejection_reason")
