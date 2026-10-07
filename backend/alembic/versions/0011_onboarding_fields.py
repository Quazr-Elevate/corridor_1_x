"""onboarding wizard fields (Tridge-style company + primary + business profile)

Revision ID: 0011_onboarding_fields
Revises: 0010_email_auth
Create Date: 2026-09-30

Adds the columns the onboarding wizard writes:

  profiles           : phone, department, position
  business_profiles  : legal_name, industry, operating_countries,
                       website_url, trade_position, seller_type,
                       business_role, export_status, target_markets,
                       target_buyer_types, main_objective,
                       company_introduction, onboarded_at
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0011_onboarding_fields"
down_revision: Union[str, None] = "0010_email_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _safe(fn):
    try:
        fn()
    except Exception:
        pass


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # ── profiles ────────────────────────────────────────────────
    _safe(lambda: op.add_column("profiles", sa.Column("phone", sa.String(length=20), nullable=True)))
    _safe(lambda: op.add_column("profiles", sa.Column("department", sa.String(length=80), nullable=True)))
    _safe(lambda: op.add_column("profiles", sa.Column("position", sa.String(length=120), nullable=True)))

    # ── business_profiles ──────────────────────────────────────
    if dialect == "postgresql":
        string_array = postgresql.ARRAY(sa.String(length=3))
        buyer_array = postgresql.ARRAY(sa.String(length=40))
    else:
        string_array = sa.String(length=1000)
        buyer_array = sa.String(length=1000)

    _safe(lambda: op.add_column("business_profiles", sa.Column("legal_name", sa.String(length=200), nullable=True)))
    _safe(lambda: op.add_column("business_profiles", sa.Column("industry", sa.String(length=120), nullable=True)))
    _safe(lambda: op.add_column("business_profiles", sa.Column("operating_countries", string_array, nullable=True)))
    _safe(lambda: op.add_column("business_profiles", sa.Column("website_url", sa.String(length=300), nullable=True)))

    _safe(lambda: op.add_column("business_profiles", sa.Column("trade_position", sa.String(length=40), nullable=True)))
    _safe(lambda: op.add_column("business_profiles", sa.Column("seller_type", sa.String(length=60), nullable=True)))
    _safe(lambda: op.add_column("business_profiles", sa.Column("business_role", sa.String(length=60), nullable=True)))
    _safe(lambda: op.add_column("business_profiles", sa.Column("export_status", sa.String(length=40), nullable=True)))
    _safe(lambda: op.add_column("business_profiles", sa.Column("target_markets", string_array, nullable=True)))
    _safe(lambda: op.add_column("business_profiles", sa.Column("target_buyer_types", buyer_array, nullable=True)))
    _safe(lambda: op.add_column("business_profiles", sa.Column("main_objective", sa.String(length=200), nullable=True)))
    _safe(lambda: op.add_column("business_profiles", sa.Column("company_introduction", sa.Text(), nullable=True)))

    _safe(lambda: op.add_column("business_profiles", sa.Column("onboarded_at", sa.DateTime(timezone=True), nullable=True)))


def downgrade() -> None:
    for col in (
        "phone",
        "department",
        "position",
    ):
        _safe(lambda c=col: op.drop_column("profiles", c))
    for col in (
        "legal_name",
        "industry",
        "operating_countries",
        "website_url",
        "trade_position",
        "seller_type",
        "business_role",
        "export_status",
        "target_markets",
        "target_buyer_types",
        "main_objective",
        "company_introduction",
        "onboarded_at",
    ):
        _safe(lambda c=col: op.drop_column("business_profiles", c))
