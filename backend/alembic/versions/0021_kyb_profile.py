"""KYB profile: kyb_document_types, encrypted KYB entries, logo/banner, quick tour

Revision ID: 0021_kyb_profile
Revises: 0020_exchange_rates
Create Date: 2026-10-24

Implements docs/04_data_model.md → "KYB profile (0021)":

* new table ``kyb_document_types`` (admin-managed per-country list) seeded
  with India (GSTIN, PAN, Udyam, IEC, FSSAI) and UAE (trade licence, TRN);
  never an Aadhaar type (``ck_kyb_document_types_no_aadhaar``);
* ``business_documents`` becomes one KYB entry: ``document_type_id`` (null =
  "Other"), encrypted value (``value_encrypted`` / ``value_key_version`` /
  ``value_hash`` / ``value_last4`` / ``value_unique``), file columns now
  optional, ``updated_at``; new checks and partial unique indexes;
* ``businesses.logo_key`` / ``banner_key``; ``users.tour_completed_at``.

Existing documents keep their file and name and show as "Other".
Portable (Postgres + SQLite batch ops). Reversible, except that downgrade
deletes value-only entries (the old table required a file).
"""
from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021_kyb_profile"
down_revision: Union[str, None] = "0020_exchange_rates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FILE_COLS = ("original_filename", "storage_key", "mime_type", "size_bytes")
_VALUE_COLS = ("value_encrypted", "value_key_version", "value_hash", "value_last4")


def _all_or_none(cols: tuple[str, ...]) -> str:
    return f"({' AND '.join(f'{c} IS NULL' for c in cols)}) OR ({' AND '.join(f'{c} IS NOT NULL' for c in cols)})"


# Frozen seed (migrations must not import app code).
# (country, code, name, input_kind, pattern, placeholder, help, mandatory, sort)
SEED = (
    ("IN", "gstin", "GSTIN", "value", r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]", "22AAAAA0000A1Z5",
     "15-character GST Identification Number", True, 10),
    ("IN", "pan", "PAN", "value", r"[A-Z]{5}[0-9]{4}[A-Z]", "AAAAA0000A",
     "Permanent Account Number of the business", True, 20),
    ("IN", "udyam", "Udyam (MSME) registration", "value", r"UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}", "UDYAM-KA-01-0000000",
     None, False, 30),
    ("IN", "iec", "Import Export Code (IEC)", "value", r"[A-Z0-9]{10}", "AAAAA0000A",
     "Needed to export outside India", False, 40),
    ("IN", "fssai", "FSSAI licence", "value_and_file", r"[0-9]{14}", "10000000000000",
     "14-digit licence number and a copy of the licence", False, 50),
    ("AE", "trade_licence", "Trade licence", "file", None, None,
     "Copy of the valid trade licence", True, 10),
    ("AE", "trn", "Tax Registration Number (VAT)", "value", r"[0-9]{15}", "100000000000003",
     "15-digit UAE VAT TRN", False, 20),
)


def upgrade() -> None:
    # 1. kyb_document_types ─────────────────────────────────────────────
    kind = sa.Enum("value", "file", "value_or_file", "value_and_file", name="kyb_input_kind")
    types = op.create_table(
        "kyb_document_types",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("country", sa.CHAR(2), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("input_kind", kind, nullable=False),
        sa.Column("value_pattern", sa.String(200), nullable=True),
        sa.Column("value_placeholder", sa.String(60), nullable=True),
        sa.Column("help_text", sa.String(300), nullable=True),
        sa.Column("is_mandatory", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_unique", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("country", "code", name="uq_kyb_document_types_country_code"),
        sa.CheckConstraint("length(country) = 2", name="ck_kyb_document_types_country"),
        sa.CheckConstraint("length(code) > 0", name="ck_kyb_document_types_code"),
        sa.CheckConstraint("code NOT IN ('aadhaar', 'aadhar')", name="ck_kyb_document_types_no_aadhaar"),
    )
    op.create_index("ix_kyb_document_types_dropdown", "kyb_document_types", ["country", "active", "sort_order"])
    op.bulk_insert(
        types,
        [
            {
                "id": uuid.uuid4(), "country": c, "code": code, "name": name, "input_kind": k,
                "value_pattern": pat, "value_placeholder": ph, "help_text": help_, "is_mandatory": mand,
                "is_unique": True, "sort_order": sort, "active": True,
            }
            for c, code, name, k, pat, ph, help_, mand, sort in SEED
        ],
    )

    # 2. businesses / users ─────────────────────────────────────────────
    with op.batch_alter_table("businesses") as batch:
        batch.add_column(sa.Column("logo_key", sa.String(400), nullable=True))
        batch.add_column(sa.Column("banner_key", sa.String(400), nullable=True))
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("tour_completed_at", sa.DateTime(timezone=True), nullable=True))

    # 3. business_documents → KYB entries ──────────────────────────────
    with op.batch_alter_table("business_documents") as batch:
        batch.add_column(sa.Column("document_type_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("value_encrypted", sa.Text(), nullable=True))
        batch.add_column(sa.Column("value_key_version", sa.SmallInteger(), nullable=True))
        batch.add_column(sa.Column("value_hash", sa.CHAR(64), nullable=True))
        batch.add_column(sa.Column("value_last4", sa.String(4), nullable=True))
        batch.add_column(sa.Column("value_unique", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
        )
        for col, typ in (
            ("original_filename", sa.String(300)),
            ("storage_key", sa.String(400)),
            ("mime_type", sa.String(120)),
            ("size_bytes", sa.Integer()),
        ):
            batch.alter_column(col, existing_type=typ, nullable=True)
        batch.drop_constraint("ck_business_documents_size", type_="check")
        batch.create_check_constraint(
            "ck_business_documents_size", "size_bytes IS NULL OR (size_bytes > 0 AND size_bytes <= 10485760)"
        )
        batch.create_check_constraint(
            "ck_business_documents_has_content", "value_encrypted IS NOT NULL OR storage_key IS NOT NULL"
        )
        batch.create_check_constraint("ck_business_documents_file_complete", _all_or_none(_FILE_COLS))
        batch.create_check_constraint("ck_business_documents_value_complete", _all_or_none(_VALUE_COLS))
        batch.create_check_constraint("ck_business_documents_doc_type", "length(doc_type) > 0")
        batch.create_foreign_key(
            "fk_business_documents_document_type_id",
            "kyb_document_types",
            ["document_type_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    op.create_index(
        "uq_business_documents_business_type",
        "business_documents",
        ["business_id", "document_type_id"],
        unique=True,
        sqlite_where=sa.text("document_type_id IS NOT NULL"),
        postgresql_where=sa.text("document_type_id IS NOT NULL"),
    )
    unique_where = sa.text("value_unique AND value_hash IS NOT NULL AND status <> 'rejected'")
    op.create_index(
        "uq_business_documents_unique_value",
        "business_documents",
        ["document_type_id", "value_hash"],
        unique=True,
        sqlite_where=unique_where,
        postgresql_where=unique_where,
    )


def downgrade() -> None:
    op.drop_index("uq_business_documents_unique_value", table_name="business_documents")
    op.drop_index("uq_business_documents_business_type", table_name="business_documents")
    # The old table required a file: value-only entries cannot survive.
    op.execute("DELETE FROM business_documents WHERE storage_key IS NULL")
    with op.batch_alter_table("business_documents") as batch:
        batch.drop_constraint("fk_business_documents_document_type_id", type_="foreignkey")
        for name in (
            "ck_business_documents_doc_type",
            "ck_business_documents_value_complete",
            "ck_business_documents_file_complete",
            "ck_business_documents_has_content",
            "ck_business_documents_size",
        ):
            batch.drop_constraint(name, type_="check")
        batch.create_check_constraint("ck_business_documents_size", "size_bytes > 0 AND size_bytes <= 10485760")
        for col, typ in (
            ("original_filename", sa.String(300)),
            ("storage_key", sa.String(400)),
            ("mime_type", sa.String(120)),
            ("size_bytes", sa.Integer()),
        ):
            batch.alter_column(col, existing_type=typ, nullable=False)
        for col in (
            "updated_at", "value_unique", "value_last4", "value_hash", "value_key_version",
            "value_encrypted", "document_type_id",
        ):
            batch.drop_column(col)

    with op.batch_alter_table("users") as batch:
        batch.drop_column("tour_completed_at")
    with op.batch_alter_table("businesses") as batch:
        batch.drop_column("banner_key")
        batch.drop_column("logo_key")

    op.drop_index("ix_kyb_document_types_dropdown", table_name="kyb_document_types")
    op.drop_table("kyb_document_types")
    sa.Enum(name="kyb_input_kind").drop(op.get_bind(), checkfirst=True)
