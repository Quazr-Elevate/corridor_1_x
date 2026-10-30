"""country-scoped document requirements catalog

Revision ID: 0021_country_doc_requirements
Revises: 0020_exchange_rates
Create Date: 2026-10-30

Adds the admin-managed catalog of which documents each country requires
during KYB, plus the FK from an uploaded document to the catalog row it
fills.

* new table ``business_document_requirements`` — one row per
  (country_code, slug) KYB cares about: ``display_name``, optional
  ``description`` / ``help_url``, ``is_mandatory`` / ``is_active`` flags,
  and audit (``created_by`` / ``updated_by`` admin email strings).
  Partial unique on (country_code, slug) WHERE is_active — soft-deleted
  rows don't block re-adding the same (country, slug) later.

* ``business_documents.required_doc_type_id`` — nullable FK into the
  catalog. NULL = user-supplied custom certification. ON DELETE SET NULL
  so retiring a requirement leaves the uploaded file intact.

Catalog is NOT seeded in-migration — super admin seeds through the admin
console (Option A).

Portable (Postgres + SQLite via batch ops). Reversible: downgrade drops
the FK column and the table.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021_country_doc_requirements"
down_revision: Union[str, None] = "0020_exchange_rates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. business_document_requirements ─────────────────────────────────
    op.create_table(
        "business_document_requirements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("country_code", sa.CHAR(2), nullable=False),
        sa.Column("slug", sa.String(40), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("help_url", sa.String(500), nullable=True),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("updated_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("length(country_code) = 2", name="ck_bdr_country_code"),
    )
    op.create_index(
        "ux_bdr_country_slug_active",
        "business_document_requirements",
        ["country_code", "slug"],
        unique=True,
        sqlite_where=sa.text("is_active = 1"),
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index(
        "ix_bdr_country_active",
        "business_document_requirements",
        ["country_code", "is_active"],
    )

    # 2. business_documents.required_doc_type_id ─────────────────────────
    with op.batch_alter_table("business_documents") as batch:
        batch.add_column(sa.Column("required_doc_type_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_business_documents_required_doc_type_id",
            "business_document_requirements",
            ["required_doc_type_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        "ix_business_documents_required_doc_type_id",
        "business_documents",
        ["required_doc_type_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_business_documents_required_doc_type_id", table_name="business_documents")
    with op.batch_alter_table("business_documents") as batch:
        batch.drop_constraint("fk_business_documents_required_doc_type_id", type_="foreignkey")
        batch.drop_column("required_doc_type_id")

    op.drop_index("ix_bdr_country_active", table_name="business_document_requirements")
    op.drop_index("ux_bdr_country_slug_active", table_name="business_document_requirements")
    op.drop_table("business_document_requirements")
