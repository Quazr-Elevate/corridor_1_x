"""Listing review, commercial terms, specification templates, certificates

Revision ID: 0026_listing_review
Revises: 0025_totp_columns
Create Date: 2026-11-15

Build plan section 03 (CX-071, CX-073, CX-074, CX-075).

* ``products`` — ``status`` (draft | under_review | published | rejected |
  paused) with the review trail, ``pending_revision`` for edits to a
  published listing, and the commercial terms: grade, HS code, origin
  country, incoterms, ``price_max`` (``price_per_unit`` becomes the range
  minimum), price validity, lead time, monthly capacity, port of loading.
* ``spec_parameters`` / ``product_specs`` — the category template and the
  seller's values.
* ``certificate_types`` / ``product_certificates`` /
  ``certificate_downloads`` — listing documents, admin-approved downloads
  and the download log.

Backfill: listings of verified businesses were already live in the market,
so they become ``published`` (``published_at`` = ``created_at``); every
other listing becomes ``draft``. Existing prices become a one-point range
(``price_max`` = ``price_per_unit``), and ``origin_country`` is set to IN
where an origin state exists (every state stored so far is Indian).

Seeds the default templates (Rice, Spices, Pulses; three certificate types).
Portable (Postgres + SQLite batch ops). Reversible: downgrade drops the new
tables and columns; listing status and templates are lost.
"""
from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026_listing_review"
down_revision: Union[str, None] = "0025_totp_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOT_DELETED = sa.text("deleted_at IS NULL")

# Frozen copies of app/modules/catalog/seed.py as of this revision.
SPECS = (
    ("Rice", "moisture", "Moisture", "%", "MAX", True, 10),
    ("Rice", "broken_grains", "Broken grains", "%", "MAX", True, 20),
    ("Rice", "foreign_matter", "Foreign matter", "%", "MAX", True, 30),
    ("Rice", "grain_length", "Grain length", "mm", "MIN", True, 40),
    ("Spices", "moisture", "Moisture", "%", "MAX", False, 10),
    ("Spices", "volatile_oil", "Volatile oil", "%", "MIN", False, 20),
    ("Spices", "total_ash", "Total ash", "%", "MAX", False, 30),
    ("Spices", "foreign_matter", "Foreign matter", "%", "MAX", False, 40),
    ("Pulses", "moisture", "Moisture", "%", "MAX", False, 10),
    ("Pulses", "foreign_matter", "Foreign matter", "%", "MAX", False, 20),
    ("Pulses", "damaged_grains", "Damaged grains", "%", "MAX", False, 30),
    ("Pulses", "weevilled_grains", "Weevilled grains", "%", "MAX", False, 40),
)
CERTIFICATES = (
    ("*", "coa", "Certificate of analysis (COA)", "Lab-issued, with the batch or lot number.", 10),
    ("*", "quality_test_report", "Quality test report", "Third-party report, within its validity.", 20),
    ("*", "product_certificate", "Product certificate", "For example FSSAI, Organic or Fair-Trade.", 30),
)

PRODUCT_COLUMNS = (
    sa.Column("grade", sa.String(100), nullable=True),
    sa.Column("hs_code", sa.String(10), nullable=True),
    sa.Column("origin_country", sa.CHAR(2), nullable=True),
    sa.Column("incoterms", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column("price_max", sa.Numeric(12, 2), nullable=True),
    sa.Column("price_usd_max", sa.Numeric(14, 2), nullable=True),
    sa.Column("price_valid_until", sa.Date(), nullable=True),
    sa.Column("lead_time_days", sa.Integer(), nullable=True),
    sa.Column("capacity_per_month", sa.Numeric(12, 2), nullable=True),
    sa.Column("capacity_unit", sa.String(10), nullable=True),
    sa.Column("port_of_loading", sa.String(100), nullable=True),
    sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
    sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("reviewed_by", sa.Uuid(), nullable=True),
    sa.Column("rejection_reason", sa.String(500), nullable=True),
    sa.Column("pending_revision", sa.JSON(), nullable=True),
    sa.Column("revision_submitted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("revision_rejection_reason", sa.String(500), nullable=True),
)
PRODUCT_CHECKS = (
    ("ck_products_status", "status IN ('draft', 'under_review', 'published', 'rejected', 'paused')"),
    ("ck_products_price_range", "price_max IS NULL OR (price_per_unit IS NOT NULL AND price_max >= price_per_unit)"),
    ("ck_products_lead_time", "lead_time_days IS NULL OR lead_time_days >= 0"),
    ("ck_products_capacity", "capacity_per_month IS NULL OR capacity_per_month >= 0"),
)


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def upgrade() -> None:
    with op.batch_alter_table("products") as batch:
        for column in PRODUCT_COLUMNS:
            batch.add_column(column.copy())
        for name, condition in PRODUCT_CHECKS:
            batch.create_check_constraint(name, condition)
        batch.create_foreign_key("fk_products_reviewed_by", "admin_users", ["reviewed_by"], ["id"], ondelete="SET NULL")
    op.create_index(
        "ix_products_review_queue", "products", ["status", "submitted_at"],
        sqlite_where=NOT_DELETED, postgresql_where=NOT_DELETED,
    )

    # Listings already live in the market stay live.
    op.execute(
        "UPDATE products SET status = 'published', published_at = created_at "
        "WHERE deleted_at IS NULL AND business_id IN ("
        "SELECT id FROM businesses WHERE verification_status = 'verified' AND deleted_at IS NULL)"
    )
    op.execute(
        "UPDATE products SET price_max = price_per_unit, price_usd_max = price_usd WHERE price_per_unit IS NOT NULL"
    )
    op.execute("UPDATE products SET origin_country = 'IN' WHERE origin_state IS NOT NULL")

    spec_parameters = op.create_table(
        "spec_parameters",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("value_type", sa.String(10), nullable=False, server_default="number"),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("default_operator", sa.String(3), nullable=False, server_default="MAX"),
        sa.Column("test_method", sa.String(100), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.CheckConstraint("value_type IN ('number', 'text')", name="ck_spec_parameters_value_type"),
        sa.CheckConstraint("default_operator IN ('MIN', 'MAX', 'EQ')", name="ck_spec_parameters_default_operator"),
        sa.CheckConstraint("code = lower(code)", name="ck_spec_parameters_code_lowercase"),
    )
    op.create_index("uq_spec_parameters_category_code", "spec_parameters", ["category", "code"], unique=True)

    op.create_table(
        "product_specs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id", ondelete="CASCADE", name="fk_product_specs_product_id"), nullable=False),
        sa.Column("parameter_id", sa.Uuid(), sa.ForeignKey("spec_parameters.id", ondelete="RESTRICT", name="fk_product_specs_parameter_id"), nullable=False),
        sa.Column("value_number", sa.Numeric(14, 4), nullable=True),
        sa.Column("value_text", sa.String(200), nullable=True),
        sa.Column("operator", sa.String(3), nullable=False),
        sa.Column("test_method", sa.String(100), nullable=True),
        sa.CheckConstraint("operator IN ('MIN', 'MAX', 'EQ')", name="ck_product_specs_operator"),
        sa.CheckConstraint("(value_number IS NULL) <> (value_text IS NULL)", name="ck_product_specs_one_value"),
    )
    op.create_index("uq_product_specs_product_parameter", "product_specs", ["product_id", "parameter_id"], unique=True)

    certificate_types = op.create_table(
        "certificate_types",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("help_text", sa.String(300), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.CheckConstraint("code = lower(code)", name="ck_certificate_types_code_lowercase"),
    )
    op.create_index("uq_certificate_types_category_code", "certificate_types", ["category", "code"], unique=True)

    op.create_table(
        "product_certificates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id", ondelete="CASCADE", name="fk_product_certificates_product_id"), nullable=False),
        sa.Column("certificate_type_id", sa.Uuid(), sa.ForeignKey("certificate_types.id", ondelete="RESTRICT", name="fk_product_certificates_certificate_type_id"), nullable=False),
        sa.Column("storage_key", sa.String(400), nullable=False),
        sa.Column("original_filename", sa.String(300), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("visibility", sa.String(15), nullable=False, server_default="internal"),
        sa.Column("visibility_set_by", sa.Uuid(), sa.ForeignKey("admin_users.id", ondelete="SET NULL", name="fk_product_certificates_visibility_set_by"), nullable=True),
        sa.Column("visibility_set_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uploaded_by_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_product_certificates_uploaded_by_user_id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("visibility IN ('internal', 'downloadable')", name="ck_product_certificates_visibility"),
        sa.CheckConstraint("size_bytes > 0", name="ck_product_certificates_size"),
    )
    op.create_index(
        "uq_product_certificates_product_type", "product_certificates", ["product_id", "certificate_type_id"], unique=True
    )

    op.create_table(
        "certificate_downloads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("certificate_id", sa.Uuid(), sa.ForeignKey("product_certificates.id", ondelete="CASCADE", name="fk_certificate_downloads_certificate_id"), nullable=False),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id", ondelete="CASCADE", name="fk_certificate_downloads_product_id"), nullable=False),
        sa.Column("buyer_business_id", sa.Uuid(), sa.ForeignKey("businesses.id", ondelete="CASCADE", name="fk_certificate_downloads_buyer_business_id"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_certificate_downloads_user_id"), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_certificate_downloads_certificate", "certificate_downloads", ["certificate_id", sa.text("downloaded_at DESC")])
    op.create_index("ix_certificate_downloads_buyer", "certificate_downloads", ["buyer_business_id", sa.text("downloaded_at DESC")])

    op.bulk_insert(
        spec_parameters,
        [
            {"id": uuid.uuid4(), "category": category, "code": code, "name": name, "value_type": "number", "unit": unit,
             "default_operator": operator, "is_required": required, "sort_order": sort, "active": True}
            for category, code, name, unit, operator, required, sort in SPECS
        ],
    )
    op.bulk_insert(
        certificate_types,
        [
            {"id": uuid.uuid4(), "category": category, "code": code, "name": name, "help_text": help_text,
             "is_required": False, "sort_order": sort, "active": True}
            for category, code, name, help_text, sort in CERTIFICATES
        ],
    )


def downgrade() -> None:
    op.drop_table("certificate_downloads")
    op.drop_table("product_certificates")
    op.drop_table("certificate_types")
    op.drop_table("product_specs")
    op.drop_table("spec_parameters")
    op.drop_index("ix_products_review_queue", table_name="products")
    with op.batch_alter_table("products") as batch:
        batch.drop_constraint("fk_products_reviewed_by", type_="foreignkey")
        for name, _ in PRODUCT_CHECKS:
            batch.drop_constraint(name, type_="check")
        for column in reversed(PRODUCT_COLUMNS):
            batch.drop_column(column.name)
