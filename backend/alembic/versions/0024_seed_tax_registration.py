"""seed a second mandatory doc requirement per country (tax_registration)

Revision ID: 0024_seed_tax_registration
Revises: 0023_reject_items
Create Date: 2026-10-30

Adds "Tax registration certificate" as a second mandatory KYB doc for every
country Cor1x currently serves. Lets the admin flow exercise a true
multi-slot review — the trader uploads two docs, admin can approve one and
reject the other with a specific reason.

Follows the same shape as 0022_seed_doc_requirements: idempotent (skips
countries that already have the slug), reversible (downgrade removes
exactly these rows).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "0024_seed_tax_registration"
down_revision: Union[str, None] = "0023_reject_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SEED_SLUG = "tax_registration"
SEED_DISPLAY_NAME = "Tax registration certificate"
SEED_DESCRIPTION = (
    "Scanned proof of tax registration with your local authority "
    "(GSTIN / VAT / EIN / etc.) — PDF, JPG or PNG."
)
SEED_ADMIN_EMAIL = "system@cor1x.local"

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
    existing = set(
        bind.execute(sa.select(_bdr.c.country_code).where(_bdr.c.slug == SEED_SLUG)).scalars()
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
    op.execute(
        sa.delete(_bdr).where(
            sa.and_(
                _bdr.c.slug == SEED_SLUG,
                _bdr.c.created_by == SEED_ADMIN_EMAIL,
            )
        )
    )
