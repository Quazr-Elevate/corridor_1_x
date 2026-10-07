"""temp_credentials table + users.must_change_password

Revision ID: 0017_temp_credentials
Revises: 0016_user_verification_flow
Create Date: 2026-10-07

New-signup flow replaces the magic-link email verification with a
temporary password handoff. Backing storage:

  * ``temp_credentials`` — one active row per user, holds the bcrypt
    hash of the emailed password plus expiry + attempt counter +
    consumed_at. UNIQUE on user_id so a resend overwrites.
  * ``users.must_change_password`` — flipped true on temp-password
    login, cleared once the user sets a real password at
    /dashboard/settings/password. The frontend uses this to gate
    every protected route behind the password screen.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0017_temp_credentials"
down_revision: Union[str, None] = "0016_user_verification_flow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "temp_credentials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "consumed_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_temp_credentials_user_id",
        "temp_credentials",
        ["user_id"],
    )

    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
    op.drop_index("ix_temp_credentials_user_id", table_name="temp_credentials")
    op.drop_table("temp_credentials")
