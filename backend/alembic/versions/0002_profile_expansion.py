"""profile expansion — additional details, bank_details, products; relaxed buyer NOT NULLs

Revision ID: 0002_profile_expansion
Revises: 0001_initial
Create Date: 2026-08-27

- Sellers gain: udyam, aadhaar, tan (Seller Details card) +
  alt_mobile, alt_email, website_url, google_business_url, facebook_url
  (Additional Details card, sellers side)
- Buyers become the unified "primary profile" for every signed-up user.
  Adds email, address_line, state, pincode, and the same additional-details
  URLs. company_name / country are relaxed to NULL since the profile is
  now created lazily as users fill sections.
- New bank_details table (one row per user, unique on user_id)
- New products table (user-owned catalog)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_profile_expansion"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── sellers: seller-specific details + additional details/social links ──
    with op.batch_alter_table("sellers") as batch:
        batch.add_column(sa.Column("udyam", sa.String(length=20), nullable=True))
        # Aadhaar is highly sensitive PII; production must move to a masked/vaulted store.
        # For dev we accept a plain 12-digit string; do not persist in real deployments.
        batch.add_column(sa.Column("aadhaar", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("tan", sa.String(length=10), nullable=True))
        batch.add_column(sa.Column("alt_mobile", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("alt_email", sa.String(length=150), nullable=True))
        batch.add_column(sa.Column("website_url", sa.String(length=300), nullable=True))
        batch.add_column(sa.Column("google_business_url", sa.String(length=300), nullable=True))
        batch.add_column(sa.Column("facebook_url", sa.String(length=300), nullable=True))

    # ── buyers: primary profile expansion ──
    with op.batch_alter_table("buyers") as batch:
        batch.add_column(sa.Column("email", sa.String(length=150), nullable=True))
        batch.add_column(sa.Column("address_line", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("state", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("pincode", sa.String(length=6), nullable=True))
        batch.add_column(sa.Column("alt_mobile", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("alt_email", sa.String(length=150), nullable=True))
        batch.add_column(sa.Column("website_url", sa.String(length=300), nullable=True))
        batch.add_column(sa.Column("google_business_url", sa.String(length=300), nullable=True))
        batch.add_column(sa.Column("facebook_url", sa.String(length=300), nullable=True))
        # Relax to NULL — profile fills in stages now
        batch.alter_column("company_name", existing_type=sa.String(length=200), nullable=True)
        batch.alter_column("country", existing_type=sa.String(length=100), nullable=True)

    # ── bank_details ──
    op.create_table(
        "bank_details",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("account_number", sa.String(length=30), nullable=False),
        sa.Column("ifsc", sa.String(length=11), nullable=False),
        sa.Column("holder_name", sa.String(length=100), nullable=False),
        sa.Column("branch_name", sa.String(length=200), nullable=True),
        sa.Column("bank_name", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ── products ──
    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("variety", sa.String(length=100), nullable=True),
        sa.Column("origin_state", sa.String(length=100), nullable=True),
        sa.Column("packaging", sa.String(length=50), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("unit", sa.String(length=10), nullable=False, server_default="MT"),
        sa.Column("moq", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("price_per_unit", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_products_user_id", "products", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_products_user_id", table_name="products")
    op.drop_table("products")
    op.drop_table("bank_details")

    with op.batch_alter_table("buyers") as batch:
        batch.alter_column("country", existing_type=sa.String(length=100), nullable=False)
        batch.alter_column("company_name", existing_type=sa.String(length=200), nullable=False)
        for col in [
            "facebook_url", "google_business_url", "website_url",
            "alt_email", "alt_mobile", "pincode", "state", "address_line", "email",
        ]:
            batch.drop_column(col)

    with op.batch_alter_table("sellers") as batch:
        for col in [
            "facebook_url", "google_business_url", "website_url",
            "alt_email", "alt_mobile", "tan", "aadhaar", "udyam",
        ]:
            batch.drop_column(col)
