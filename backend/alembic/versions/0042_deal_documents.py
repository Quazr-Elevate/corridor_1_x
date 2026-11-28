"""LOIs and contracts: templates, documents, signatures

Revision ID: 0042_deal_documents
Revises: 0041_no_builtin_india_checks
Create Date: 2026-11-28

M4 · S9, CX-104 … CX-108 (A-081); docs/04_data_model.md → "LOIs and contracts (0042)".

* new ``contract_templates``: versioned template text, draft until a super
  admin records a lawyer's approval.
* new ``deal_documents``: one rendered LOI or contract per deal, kind and
  side; its text, terms and hash are frozen by ``trg_deal_documents_frozen``.
* new ``document_signatures``: insert only (``trg_document_signatures_insert_only``).

No existing rows change. Reversible: downgrade drops the triggers and tables.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0042_deal_documents"
down_revision: Union[str, None] = "0041_no_builtin_india_checks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# As of this revision (DOCUMENT_FROZEN in the model).
FROZEN = ("deal_id", "kind", "side", "term_sheet_id", "template_id", "body", "content_sha256", "terms",
          "value_minor", "currency")


def _triggers(dialect: str) -> list[str]:
    if dialect == "sqlite":
        changed = " OR ".join(f"NEW.{c} IS NOT OLD.{c}" for c in FROZEN)
        return [
            f"CREATE TRIGGER trg_deal_documents_frozen BEFORE UPDATE ON deal_documents WHEN {changed} "
            "BEGIN SELECT RAISE(ABORT, 'deal_document_frozen'); END",
            "CREATE TRIGGER trg_document_signatures_insert_only BEFORE UPDATE ON document_signatures "
            "BEGIN SELECT RAISE(ABORT, 'signature_insert_only'); END",
        ]
    # json has no equality operator in Postgres: compare its text.
    changed = " OR ".join(
        f"NEW.{c}::text IS DISTINCT FROM OLD.{c}::text" if c == "terms" else f"NEW.{c} IS DISTINCT FROM OLD.{c}"
        for c in FROZEN
    )
    return [
        "CREATE FUNCTION deal_documents_frozen() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
        f"IF {changed} THEN RAISE EXCEPTION 'deal_document_frozen' USING ERRCODE = 'integrity_constraint_violation'; "
        "END IF; RETURN NEW; END $$",
        "CREATE TRIGGER trg_deal_documents_frozen BEFORE UPDATE ON deal_documents "
        "FOR EACH ROW EXECUTE FUNCTION deal_documents_frozen()",
        "CREATE FUNCTION document_signatures_insert_only() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
        "RAISE EXCEPTION 'signature_insert_only' USING ERRCODE = 'integrity_constraint_violation'; END $$",
        "CREATE TRIGGER trg_document_signatures_insert_only BEFORE UPDATE ON document_signatures "
        "FOR EACH ROW EXECUTE FUNCTION document_signatures_insert_only()",
    ]


def upgrade() -> None:
    op.create_table(
        "contract_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approval_note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("code IN ('loi_buy', 'loi_sell', 'sales', 'purchase')", name="ck_contract_templates_code"),
        sa.CheckConstraint("status IN ('draft', 'approved', 'retired')", name="ck_contract_templates_status"),
        sa.CheckConstraint(
            "status <> 'approved' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL AND approval_note IS NOT NULL)",
            name="ck_contract_templates_approval",
        ),
        sa.ForeignKeyConstraint(["approved_by"], ["admin_users.id"], ondelete="SET NULL", name="fk_contract_templates_approved_by"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", "version", name="uq_contract_templates_code_version"),
    )
    op.create_table(
        "deal_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("side", sa.String(6), nullable=False),
        sa.Column("term_sheet_id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.CHAR(64), nullable=False),
        sa.Column("terms", sa.JSON(), nullable=False),
        sa.Column("value_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("void_reason", sa.String(200), nullable=True),
        sa.Column("issued_by", sa.Uuid(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('loi', 'contract')", name="ck_deal_documents_kind"),
        sa.CheckConstraint("side IN ('buyer', 'seller')", name="ck_deal_documents_side"),
        sa.CheckConstraint(
            "status IN ('issued', 'party_signed', 'signed', 'effective', 'void')", name="ck_deal_documents_status"
        ),
        sa.CheckConstraint("status <> 'effective' OR kind = 'contract'", name="ck_deal_documents_effective_contract"),
        sa.CheckConstraint("status <> 'void' OR void_reason IS NOT NULL", name="ck_deal_documents_void_reason"),
        sa.CheckConstraint("value_minor > 0", name="ck_deal_documents_value"),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="RESTRICT", name="fk_deal_documents_deal_id"),
        sa.ForeignKeyConstraint(["term_sheet_id"], ["term_sheets.id"], ondelete="RESTRICT", name="fk_deal_documents_term_sheet_id"),
        sa.ForeignKeyConstraint(
            ["template_id"], ["contract_templates.id"], ondelete="RESTRICT", name="fk_deal_documents_template_id"
        ),
        sa.ForeignKeyConstraint(["issued_by"], ["admin_users.id"], ondelete="SET NULL", name="fk_deal_documents_issued_by"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_deal_documents_live", "deal_documents", ["deal_id", "kind", "side"], unique=True,
        sqlite_where=sa.text("status <> 'void'"), postgresql_where=sa.text("status <> 'void'"),
    )
    op.create_index("ix_deal_documents_expiry", "deal_documents", ["status", "expires_at"])
    op.create_table(
        "document_signatures",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("signer_type", sa.String(8), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("admin_id", sa.Uuid(), nullable=True),
        sa.Column("signer_role", sa.String(100), nullable=False),
        sa.Column("authority_confirmed", sa.Boolean(), nullable=False),
        sa.Column("content_sha256", sa.CHAR(64), nullable=False),
        sa.Column("ip_prefix", sa.String(50), nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("signer_type IN ('party', 'corridor')", name="ck_document_signatures_signer_type"),
        sa.CheckConstraint(
            "(signer_type = 'party' AND user_id IS NOT NULL AND admin_id IS NULL) OR "
            "(signer_type = 'corridor' AND admin_id IS NOT NULL AND user_id IS NULL)",
            name="ck_document_signatures_signer",
        ),
        sa.CheckConstraint("authority_confirmed", name="ck_document_signatures_authority"),
        sa.ForeignKeyConstraint(
            ["document_id"], ["deal_documents.id"], ondelete="RESTRICT", name="fk_document_signatures_document_id"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT", name="fk_document_signatures_user_id"),
        sa.ForeignKeyConstraint(["admin_id"], ["admin_users.id"], ondelete="RESTRICT", name="fk_document_signatures_admin_id"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "signer_type", name="uq_document_signatures_document_signer"),
    )
    for sql in _triggers(op.get_bind().dialect.name):
        op.execute(sql)


def downgrade() -> None:
    pg = op.get_bind().dialect.name == "postgresql"
    for trigger, table in (("trg_document_signatures_insert_only", "document_signatures"),
                           ("trg_deal_documents_frozen", "deal_documents")):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger}" + (f" ON {table}" if pg else ""))
    if pg:
        op.execute("DROP FUNCTION IF EXISTS document_signatures_insert_only()")
        op.execute("DROP FUNCTION IF EXISTS deal_documents_frozen()")
    op.drop_table("document_signatures")
    op.drop_index("ix_deal_documents_expiry", table_name="deal_documents")
    op.drop_index("uq_deal_documents_live", table_name="deal_documents")
    op.drop_table("deal_documents")
    op.drop_table("contract_templates")
