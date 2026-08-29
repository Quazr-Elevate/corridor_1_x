"""per-field verification timestamps

Revision ID: 0009_field_verification
Revises: 0008_contact_reveals
Create Date: 2026-08-29

Adds `*_verified_at` columns so we stop trusting "the row has a value"
as proof of verification. From this migration on, every mutable
contact / identifier is written atomically with its verified_at stamp
via the /verify/* endpoints; a NULL verified_at means the value is
either absent or unverified (treated the same by the UI).

Backfill: any existing non-null value predates this migration and was
accepted under the old trust-on-save regime. We stamp them at "now"
so existing accounts stay usable without a mass re-verify — but new
writes go through the verify endpoints.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009_field_verification"
down_revision: Union[str, None] = "0008_contact_reveals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PROFILE_FIELDS = (
    ("email", "email_verified_at"),
    ("alt_mobile", "alt_mobile_verified_at"),
    ("alt_email", "alt_email_verified_at"),
    ("business_email", "business_email_verified_at"),
)

BUSINESS_FIELDS = (
    ("gstin", "gstin_verified_at"),
    ("pan", "pan_verified_at"),
    ("bank_ifsc", "ifsc_verified_at"),
)


def upgrade() -> None:
    for _, stamp in PROFILE_FIELDS:
        op.add_column("profiles", sa.Column(stamp, sa.DateTime(timezone=True), nullable=True))
    for _, stamp in BUSINESS_FIELDS:
        op.add_column(
            "business_profiles", sa.Column(stamp, sa.DateTime(timezone=True), nullable=True)
        )

    # Backfill: existing non-null values are grandfathered — mark them
    # verified at CURRENT_TIMESTAMP so profile pages don't suddenly
    # force re-verify. CURRENT_TIMESTAMP is portable across SQLite + Postgres.
    for value_col, stamp in PROFILE_FIELDS:
        op.execute(
            f"UPDATE profiles SET {stamp} = CURRENT_TIMESTAMP "
            f"WHERE {value_col} IS NOT NULL"
        )
    for value_col, stamp in BUSINESS_FIELDS:
        op.execute(
            f"UPDATE business_profiles SET {stamp} = CURRENT_TIMESTAMP "
            f"WHERE {value_col} IS NOT NULL"
        )


def downgrade() -> None:
    for _, stamp in BUSINESS_FIELDS:
        op.drop_column("business_profiles", stamp)
    for _, stamp in PROFILE_FIELDS:
        op.drop_column("profiles", stamp)
