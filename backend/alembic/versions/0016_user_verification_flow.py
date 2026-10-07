"""users: pending_verification status + review audit columns

Revision ID: 0016_user_verification_flow
Revises: 0015_doc_rejection_reason
Create Date: 2026-10-05

Adds the state + audit trail needed for the "Verified" badge flow:

  * ``pending_verification`` — new enum value between ``active`` and
    ``verified``. Backend flips the user into it automatically once the
    seven mandatory profile fields are all filled.
  * ``verification_submitted_at`` — the moment that auto-flip happened.
  * ``verified_at`` — the admin-approval timestamp.
  * ``verification_rejected_reason`` — admin's note when the badge is
    denied; surfaced to the user through the rejection popup.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0016_user_verification_flow"
down_revision: Union[str, None] = "0015_doc_rejection_reason"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # 1. Extend the enum --------------------------------------------
    # On Postgres we ALTER TYPE; on SQLite the enum is just a CHECK
    # constraint and new values are accepted without a schema change.
    if dialect == "postgresql":
        op.execute(
            "ALTER TYPE user_status ADD VALUE IF NOT EXISTS 'pending_verification' "
            "BEFORE 'verified'"
        )

    # 2. Audit columns ----------------------------------------------
    op.add_column(
        "users",
        sa.Column("verification_submitted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "verification_rejected_reason", sa.String(length=500), nullable=True
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "verification_rejected_reason")
    op.drop_column("users", "verified_at")
    op.drop_column("users", "verification_submitted_at")
    # Postgres doesn't support removing a single enum value cleanly — leave
    # it in place. A full down-migration would need to recreate the type.
