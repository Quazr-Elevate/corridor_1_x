"""email-based auth — clean slate

Revision ID: 0010_email_auth
Revises: 0009_field_verification
Create Date: 2026-09-30

Swaps mobile-OTP + GSTIN/PAN onboarding for a work-email + password flow.

  - users              gains: email, business_name, password_hash, email_verified_at
                       gains 'active' and 'email_verified' statuses in the enum
  - profiles           loses: email, alt_mobile, alt_email, business_email,
                              and their *_verified_at siblings
  - business_profiles  loses: onboarding_path, gstin, gstin_verified_at,
                              pan, pan_verified_at, company_name, aadhaar, tan
  - identities         DROPPED
  - otps               DROPPED

This is a one-way migration. Data is wiped (Cor1x has no production users
yet), and the pre-0010 mobile-based rows can't be reconstructed from the
new email-based schema.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0010_email_auth"
down_revision: Union[str, None] = "0009_field_verification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _safe(sql: str) -> None:
    """Run a DDL statement, swallowing "object does not exist" errors so this
    migration is idempotent across databases at slightly different states."""
    try:
        op.execute(sql)
    except Exception:
        pass


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # ── Wipe existing rows (dev — Cor1x has no production users). ───
    for table in (
        "contact_reveals",
        "products",
        "profiles",
        "business_profiles",
        "identities",
        "otps",
        "users",
    ):
        _safe(f"DELETE FROM {table}")

    # ── Drop obsolete tables ────────────────────────────────────────
    _safe("DROP TABLE IF EXISTS otps CASCADE" if dialect == "postgresql" else "DROP TABLE IF EXISTS otps")
    _safe("DROP TABLE IF EXISTS identities CASCADE" if dialect == "postgresql" else "DROP TABLE IF EXISTS identities")

    # ── users: add email-auth columns ───────────────────────────────
    # nullable=True on the two required cols so ALTER succeeds on an
    # (already empty) table; a follow-up SET NOT NULL makes them
    # required without needing a backfill.
    op.add_column("users", sa.Column("email", sa.String(length=200), nullable=True))
    op.add_column("users", sa.Column("business_name", sa.String(length=200), nullable=True))
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("users", "email", nullable=False)
    op.alter_column("users", "business_name", nullable=False)
    if dialect == "postgresql":
        _safe("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)")
    else:
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── profiles: drop contact fields moved to users / removed ──────
    for col in (
        "email",
        "email_verified_at",
        "alt_mobile",
        "alt_mobile_verified_at",
        "alt_email",
        "alt_email_verified_at",
        "business_email",
        "business_email_verified_at",
    ):
        if dialect == "postgresql":
            _safe(f"ALTER TABLE profiles DROP COLUMN IF EXISTS {col}")
        else:
            try:
                op.drop_column("profiles", col)
            except Exception:
                pass

    # ── business_profiles: strip regulated IDs and company_name ─────
    if dialect == "postgresql":
        _safe("DROP INDEX IF EXISTS ix_business_profiles_gstin")
        _safe("DROP INDEX IF EXISTS ix_business_profiles_pan")
        _safe("DROP INDEX IF EXISTS uq_business_profiles_gstin")
        _safe("DROP INDEX IF EXISTS uq_business_profiles_pan")

    for col in (
        "onboarding_path",
        "gstin",
        "gstin_verified_at",
        "pan",
        "pan_verified_at",
        "company_name",
        "aadhaar",
        "tan",
    ):
        if dialect == "postgresql":
            _safe(f"ALTER TABLE business_profiles DROP COLUMN IF EXISTS {col}")
        else:
            try:
                op.drop_column("business_profiles", col)
            except Exception:
                pass

    if dialect == "postgresql":
        _safe("DROP TYPE IF EXISTS business_onboarding_path")
        # user_status gains two new values (12+ syntax).
        _safe("ALTER TYPE user_status ADD VALUE IF NOT EXISTS 'email_verified'")
        _safe("ALTER TYPE user_status ADD VALUE IF NOT EXISTS 'active'")


def downgrade() -> None:
    raise NotImplementedError("0010 is a one-way migration.")
