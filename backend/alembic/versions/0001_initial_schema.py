"""initial schema — users, identities, sellers, buyers, otps

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-11

Matches phase 1 onboarding schema (02_onboarding_schema.md).
Portable across SQLite (dev default) and Postgres (production).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


user_type = sa.Enum("seller", "buyer", name="user_type")
user_status = sa.Enum(
    "signed_up", "profile_complete", "verified", "rejected", name="user_status"
)
seller_path = sa.Enum("gstin", "pan", name="seller_onboarding_path")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_type", user_type, nullable=False),
        sa.Column("status", user_status, nullable=False, server_default="signed_up"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "identities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("value", sa.String(length=150), nullable=False, unique=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_identities_user_id", "identities", ["user_id"])

    op.create_table(
        "sellers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("onboarding_path", seller_path, nullable=False),
        sa.Column("gstin", sa.CHAR(length=15), nullable=True),
        sa.Column("pan", sa.CHAR(length=10), nullable=False),
        sa.Column("company_name", sa.String(length=200), nullable=False),
        sa.Column("business_type", sa.String(length=100), nullable=True),
        sa.Column("nature_of_business", sa.String(length=200), nullable=True),
        sa.Column("owner_name", sa.String(length=100), nullable=False),
        sa.Column("building", sa.String(length=200), nullable=True),
        sa.Column("pincode", sa.CHAR(length=6), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("district", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=False, server_default="India"),
    )
    # Portable partial unique index — Alembic emits the right WHERE clause per dialect.
    op.create_index(
        "uq_sellers_gstin",
        "sellers",
        ["gstin"],
        unique=True,
        sqlite_where=sa.text("gstin IS NOT NULL"),
        postgresql_where=sa.text("gstin IS NOT NULL"),
    )

    op.create_table(
        "buyers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("full_name", sa.String(length=100), nullable=False),
        sa.Column("company_name", sa.String(length=200), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=True),
    )

    op.create_table(
        "otps",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "identity_id",
            sa.Uuid(),
            sa.ForeignKey("identities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("attempts", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_otps_identity_expires", "otps", ["identity_id", "expires_at"])


def downgrade() -> None:
    op.drop_index("ix_otps_identity_expires", table_name="otps")
    op.drop_table("otps")
    op.drop_table("buyers")
    op.drop_index("uq_sellers_gstin", table_name="sellers")
    op.drop_table("sellers")
    op.drop_index("ix_identities_user_id", table_name="identities")
    op.drop_table("identities")
    op.drop_table("users")

    # Drop Postgres native enum types (no-op on SQLite).
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        seller_path.drop(bind, checkfirst=True)
        user_status.drop(bind, checkfirst=True)
        user_type.drop(bind, checkfirst=True)
