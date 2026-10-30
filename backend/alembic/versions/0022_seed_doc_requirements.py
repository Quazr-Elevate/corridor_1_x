"""seed one mandatory doc requirement per country

Revision ID: 0022_seed_doc_requirements
Revises: 0021_country_doc_requirements
Create Date: 2026-10-30

Inserts one mandatory ``business_registration`` requirement per country
Cor1x currently serves (per ``frontend/components/account/countries.ts``).
Lets the catalog be useful out of the box — every business lands on a
Documents tab that already shows at least one slot. Super admin can edit
the display name or deactivate rows afterwards via the admin UI.

Idempotent: skips rows that already exist for the same (country, slug).

Portable (Postgres + SQLite). Reversible: downgrade removes exactly the
rows this script inserted (by slug), keeping any admin-created rows.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "0022_seed_doc_requirements"
down_revision: Union[str, None] = "0021_country_doc_requirements"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SEED_SLUG = "business_registration"
SEED_DISPLAY_NAME = "Business registration certificate"
SEED_DESCRIPTION = (
    "Scanned copy of the certificate that proves your business is "
    "registered with the local authority (incorporation, trade licence, "
    "or equivalent). PDF, JPG or PNG."
)
SEED_ADMIN_EMAIL = "system@cor1x.local"  # placeholder — swaps to admin FK when RBAC lands

# Mirrors the frontend COUNTRIES list.
SEED_COUNTRIES: tuple[str, ...] = (
    "IN", "AE", "SA", "OM", "QA", "KW", "BH",
    "US", "GB", "DE", "NL",
    "SG", "MY", "ID", "TH", "VN",
    "JP", "CN", "KR", "AU",
)


_bdr = sa.table(
    "business_document_requirements",
    sa.column("id", sa.Uuid()),
    sa.column("country_code", sa.CHAR(2)),
    sa.column("slug", sa.String(40)),
    sa.column("display_name", sa.String(100)),
    sa.column("description", sa.String(500)),
    sa.column("help_url", sa.String(500)),
    sa.column("is_mandatory", sa.Boolean()),
    sa.column("is_active", sa.Boolean()),
    sa.column("created_by", sa.String(200)),
    sa.column("updated_by", sa.String(200)),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(tz=timezone.utc)

    # Which countries already have this slug? (Idempotent re-run safety.)
    existing = set(
        bind.execute(
            sa.select(_bdr.c.country_code).where(_bdr.c.slug == SEED_SLUG)
        ).scalars()
    )

    rows = [
        {
            "id": uuid4(),
            "country_code": code,
            "slug": SEED_SLUG,
            "display_name": SEED_DISPLAY_NAME,
            "description": SEED_DESCRIPTION,
            "help_url": None,
            "is_mandatory": True,
            "is_active": True,
            "created_by": SEED_ADMIN_EMAIL,
            "updated_by": SEED_ADMIN_EMAIL,
            "created_at": now,
            "updated_at": now,
        }
        for code in SEED_COUNTRIES
        if code not in existing
    ]
    if rows:
        op.bulk_insert(_bdr, rows)


def downgrade() -> None:
    # Only remove the rows this script seeded — leave admin-created rows alone.
    op.execute(
        sa.delete(_bdr).where(
            sa.and_(
                _bdr.c.slug == SEED_SLUG,
                _bdr.c.created_by == SEED_ADMIN_EMAIL,
            )
        )
    )
