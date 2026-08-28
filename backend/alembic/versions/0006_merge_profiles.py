"""merge profiles: rename buyers -> profiles, sellers -> business_profiles,
fold bank_details into business_profiles, drop users.user_type

Revision ID: 0006_merge_profiles
Revises: 0005_product_photos
Create Date: 2026-08-29

Consolidates the role-and-profile split. The new shape:

- `profiles`          — every user has one (person: name, address, contacts, social)
- `business_profiles` — optional per user (business identity + bank)
- `products`          — presence of any row here means the user is a seller
- `users.user_type`   — dropped; role derived from `products`

The migration copies data from the old tables and then drops them. Because
we're pre-launch, we do this in a single migration; there is no downgrade
path that reconstructs the split (would need to guess which fields came
from where). Downgrade recreates the old shape empty.

Portable across SQLite (dev default) + Postgres (production).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_merge_profiles"
down_revision: Union[str, None] = "0005_product_photos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# New enum name to avoid clashing with the old seller_onboarding_path
# enum still cached in Postgres pg_type after prior migrations.
business_path = sa.Enum("gstin", "pan", name="business_onboarding_path")


def upgrade() -> None:
    # ─────────────────────────────────────────────────────────────
    # 1. Create the new tables (empty)
    # ─────────────────────────────────────────────────────────────

    op.create_table(
        "profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("full_name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=150), nullable=True),
        sa.Column("address_line", sa.String(length=200), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("pincode", sa.CHAR(length=6), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=False, server_default="India"),
        sa.Column("alt_mobile", sa.String(length=20), nullable=True),
        sa.Column("alt_email", sa.String(length=150), nullable=True),
        sa.Column("business_email", sa.String(length=150), nullable=True),
        sa.Column("website_url", sa.String(length=300), nullable=True),
        sa.Column("google_business_url", sa.String(length=300), nullable=True),
        sa.Column("facebook_url", sa.String(length=300), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "business_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("onboarding_path", business_path, nullable=False),
        sa.Column("gstin", sa.CHAR(length=15), nullable=True),
        sa.Column("pan", sa.CHAR(length=10), nullable=False),
        sa.Column("company_name", sa.String(length=200), nullable=False),
        sa.Column("business_type", sa.String(length=100), nullable=True),
        sa.Column("nature_of_business", sa.String(length=200), nullable=True),
        sa.Column("udyam", sa.String(length=20), nullable=True),
        sa.Column("aadhaar", sa.String(length=64), nullable=True),
        sa.Column("tan", sa.String(length=10), nullable=True),
        sa.Column("bank_account_number", sa.String(length=30), nullable=True),
        sa.Column("bank_ifsc", sa.String(length=11), nullable=True),
        sa.Column("bank_holder_name", sa.String(length=100), nullable=True),
        sa.Column("bank_branch_name", sa.String(length=200), nullable=True),
        sa.Column("bank_name", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "uq_business_profiles_gstin",
        "business_profiles",
        ["gstin"],
        unique=True,
        sqlite_where=sa.text("gstin IS NOT NULL"),
        postgresql_where=sa.text("gstin IS NOT NULL"),
    )

    # ─────────────────────────────────────────────────────────────
    # 2. Copy data from old tables into the new ones
    #
    # `buyers` rows always map to a `profiles` row.
    # For users who had BOTH a buyer and a seller row (impossible under
    # user_type = fixed-at-signup, but defensive), the buyer wins for
    # personal fields; owner_name/address from sellers are ignored.
    # Users who only had a seller row (never a buyer — shouldn't happen)
    # get a synthesised profile from seller.owner_name + address.
    # ─────────────────────────────────────────────────────────────

    bind = op.get_bind()

    # UUID literal helper — SQLite stores UUIDs as 32-char hex, Postgres as UUID.
    # sa.Uuid handles both on bind, so raw SQL with cast is easier via SQLAlchemy Core.
    from sqlalchemy import MetaData, Table, select, insert

    meta = MetaData()
    meta.reflect(bind=bind, only=["users", "buyers", "sellers", "bank_details"])
    users_t = meta.tables["users"]
    buyers_t = meta.tables["buyers"]
    sellers_t = meta.tables["sellers"]
    bank_t = meta.tables["bank_details"]

    # Reflect the freshly-created targets too.
    meta2 = MetaData()
    meta2.reflect(bind=bind, only=["profiles", "business_profiles"])
    profiles_t = meta2.tables["profiles"]
    biz_t = meta2.tables["business_profiles"]

    import uuid as _uuid

    def _new_id() -> _uuid.UUID:
        return _uuid.uuid4()

    # ── 2a. Copy every buyer into profiles ───────────────────────
    for row in bind.execute(select(buyers_t)).mappings():
        bind.execute(
            insert(profiles_t).values(
                id=_new_id(),
                user_id=row["user_id"],
                full_name=row["full_name"],
                email=row.get("email"),
                address_line=row.get("address_line"),
                city=row.get("city"),
                state=row.get("state"),
                pincode=row.get("pincode"),
                country=row.get("country") or "India",
                alt_mobile=row.get("alt_mobile"),
                alt_email=row.get("alt_email"),
                business_email=row.get("business_email"),
                website_url=row.get("website_url"),
                google_business_url=row.get("google_business_url"),
                facebook_url=row.get("facebook_url"),
            )
        )

    # ── 2b. Sellers → business_profiles + fallback profile ───────
    existing_profile_user_ids = {
        r[0] for r in bind.execute(select(profiles_t.c.user_id)).all()
    }

    for row in bind.execute(select(sellers_t)).mappings():
        uid = row["user_id"]

        # Business half
        bind.execute(
            insert(biz_t).values(
                id=_new_id(),
                user_id=uid,
                onboarding_path=row["onboarding_path"],
                gstin=row.get("gstin"),
                pan=row["pan"],
                company_name=row["company_name"],
                business_type=row.get("business_type"),
                nature_of_business=row.get("nature_of_business"),
                udyam=row.get("udyam"),
                aadhaar=row.get("aadhaar"),
                tan=row.get("tan"),
            )
        )

        # Profile half — only synthesise if user has no buyer row already
        if uid not in existing_profile_user_ids:
            bind.execute(
                insert(profiles_t).values(
                    id=_new_id(),
                    user_id=uid,
                    full_name=row["owner_name"],
                    address_line=row.get("building"),
                    city=row["city"],
                    state=row["state"],
                    pincode=row["pincode"],
                    country=row.get("country") or "India",
                    alt_mobile=row.get("alt_mobile"),
                    alt_email=row.get("alt_email"),
                    website_url=row.get("website_url"),
                    google_business_url=row.get("google_business_url"),
                    facebook_url=row.get("facebook_url"),
                )
            )
            existing_profile_user_ids.add(uid)

    # ── 2c. Fold bank_details into business_profiles ─────────────
    for row in bind.execute(select(bank_t)).mappings():
        bind.execute(
            biz_t.update()
            .where(biz_t.c.user_id == row["user_id"])
            .values(
                bank_account_number=row["account_number"],
                bank_ifsc=row["ifsc"],
                bank_holder_name=row["holder_name"],
                bank_branch_name=row.get("branch_name"),
                bank_name=row.get("bank_name"),
            )
        )

    # ─────────────────────────────────────────────────────────────
    # 3. Drop the old tables + column
    # ─────────────────────────────────────────────────────────────

    op.drop_table("bank_details")
    op.drop_table("sellers")
    op.drop_table("buyers")

    # Drop the seller_onboarding_path enum on Postgres (SQLite: no-op).
    if bind.dialect.name == "postgresql":
        sa.Enum(name="seller_onboarding_path").drop(bind, checkfirst=True)

    # Drop users.user_type + the user_type enum type.
    with op.batch_alter_table("users") as batch:
        batch.drop_column("user_type")
    if bind.dialect.name == "postgresql":
        sa.Enum(name="user_type").drop(bind, checkfirst=True)


def downgrade() -> None:
    """Recreate the old shape empty. Data written into profiles /
    business_profiles is NOT reconstructed."""
    bind = op.get_bind()

    # Add users.user_type back (nullable so existing rows survive).
    user_type = sa.Enum("seller", "buyer", name="user_type")
    if bind.dialect.name == "postgresql":
        user_type.create(bind, checkfirst=True)
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("user_type", user_type, nullable=True))

    seller_path = sa.Enum("gstin", "pan", name="seller_onboarding_path")

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
        sa.Column("email", sa.String(length=150), nullable=True),
        sa.Column("address_line", sa.String(length=200), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("pincode", sa.String(length=6), nullable=True),
        sa.Column("company_name", sa.String(length=200), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("alt_mobile", sa.String(length=20), nullable=True),
        sa.Column("alt_email", sa.String(length=150), nullable=True),
        sa.Column("business_email", sa.String(length=150), nullable=True),
        sa.Column("website_url", sa.String(length=300), nullable=True),
        sa.Column("google_business_url", sa.String(length=300), nullable=True),
        sa.Column("facebook_url", sa.String(length=300), nullable=True),
    )

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
        sa.Column("udyam", sa.String(length=20), nullable=True),
        sa.Column("aadhaar", sa.String(length=64), nullable=True),
        sa.Column("tan", sa.String(length=10), nullable=True),
        sa.Column("alt_mobile", sa.String(length=20), nullable=True),
        sa.Column("alt_email", sa.String(length=150), nullable=True),
        sa.Column("website_url", sa.String(length=300), nullable=True),
        sa.Column("google_business_url", sa.String(length=300), nullable=True),
        sa.Column("facebook_url", sa.String(length=300), nullable=True),
    )
    op.create_index(
        "uq_sellers_gstin",
        "sellers",
        ["gstin"],
        unique=True,
        sqlite_where=sa.text("gstin IS NOT NULL"),
        postgresql_where=sa.text("gstin IS NOT NULL"),
    )

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
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.drop_index("uq_business_profiles_gstin", table_name="business_profiles")
    op.drop_table("business_profiles")
    op.drop_table("profiles")

    if bind.dialect.name == "postgresql":
        business_path.drop(bind, checkfirst=True)
