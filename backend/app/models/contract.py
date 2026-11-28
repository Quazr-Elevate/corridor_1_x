"""LOIs and contracts (M4 · S9, CX-104 … CX-108, A-081).

Corridor One X is the counterparty to both sides, so every deal has two of
each document: the buyer's (Corridor One X sells) and the seller's
(Corridor One X buys). Each names only Corridor One X and its one party.

A document is rendered once, from an agreed term sheet and an approved
template, and never changes: its text, terms and hash are frozen by a
trigger. A change means voiding it and issuing a new one."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CHAR,
    DDL,
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    event,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime

TEMPLATE_CODES = ("loi_buy", "loi_sell", "sales", "purchase")
TEMPLATE_STATUSES = ("draft", "approved", "retired")
DOCUMENT_KINDS = ("loi", "contract")
#: ``issued`` → ``party_signed`` → ``signed`` (Corridor One X countersigned)
#: → ``effective`` (contracts only, both at once); ``void`` at any point
#: before effective, with a reason.
DOCUMENT_STATUSES = ("issued", "party_signed", "signed", "effective", "void")
DOCUMENT_LIVE = ("issued", "party_signed", "signed", "effective")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class ContractTemplate(Base):
    """A template version. Documents render only from an approved one: a
    super admin records the lawyer's approval (CX-108)."""

    __tablename__ = "contract_templates"
    __table_args__ = (
        UniqueConstraint("code", "version", name="uq_contract_templates_code_version"),
        CheckConstraint(_in("code", TEMPLATE_CODES), name="ck_contract_templates_code"),
        CheckConstraint(_in("status", TEMPLATE_STATUSES), name="ck_contract_templates_status"),
        CheckConstraint(
            "status <> 'approved' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL AND approval_note IS NOT NULL)",
            name="ck_contract_templates_approval",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="draft")
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("admin_users.id", ondelete="SET NULL", name="fk_contract_templates_approved_by"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    #: Who approved it and where their written approval is kept.
    approval_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())


class DealDocument(Base):
    """One LOI or contract for one side of a deal."""

    __tablename__ = "deal_documents"
    __table_args__ = (
        Index(
            "uq_deal_documents_live", "deal_id", "kind", "side", unique=True,
            sqlite_where=text("status <> 'void'"), postgresql_where=text("status <> 'void'"),
        ),
        Index("ix_deal_documents_expiry", "status", "expires_at"),
        CheckConstraint(_in("kind", DOCUMENT_KINDS), name="ck_deal_documents_kind"),
        CheckConstraint("side IN ('buyer', 'seller')", name="ck_deal_documents_side"),
        CheckConstraint(_in("status", DOCUMENT_STATUSES), name="ck_deal_documents_status"),
        CheckConstraint("status <> 'effective' OR kind = 'contract'", name="ck_deal_documents_effective_contract"),
        CheckConstraint("status <> 'void' OR void_reason IS NOT NULL", name="ck_deal_documents_void_reason"),
        CheckConstraint("value_minor > 0", name="ck_deal_documents_value"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("deals.id", ondelete="RESTRICT", name="fk_deal_documents_deal_id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(8), nullable=False)
    side: Mapped[str] = mapped_column(String(6), nullable=False)
    term_sheet_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("term_sheets.id", ondelete="RESTRICT", name="fk_deal_documents_term_sheet_id"), nullable=False
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("contract_templates.id", ondelete="RESTRICT", name="fk_deal_documents_template_id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="issued")
    #: The rendered text the party reads and signs, and its SHA-256.
    body: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    #: The structured terms the text was rendered from; the mirror validator reads these.
    terms: Mapped[dict] = mapped_column(JSON, nullable=False)
    #: Price × quantity, in this side's currency.
    value_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    #: Sign by this time or the document lapses (5 business days, A-081).
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    void_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    issued_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("admin_users.id", ondelete="SET NULL", name="fk_deal_documents_issued_by"), nullable=True
    )
    issued_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    effective_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DocumentSignature(Base):
    """A signature on the exact text read: its hash is stored with it. The
    party's signer is a user; their name stays in the vault and is read
    through ``modules/masking`` when shown. Insert only."""

    __tablename__ = "document_signatures"
    __table_args__ = (
        UniqueConstraint("document_id", "signer_type", name="uq_document_signatures_document_signer"),
        CheckConstraint("signer_type IN ('party', 'corridor')", name="ck_document_signatures_signer_type"),
        CheckConstraint(
            "(signer_type = 'party' AND user_id IS NOT NULL AND admin_id IS NULL) OR "
            "(signer_type = 'corridor' AND admin_id IS NOT NULL AND user_id IS NULL)",
            name="ck_document_signatures_signer",
        ),
        CheckConstraint("authority_confirmed", name="ck_document_signatures_authority"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("deal_documents.id", ondelete="RESTRICT", name="fk_document_signatures_document_id"),
        nullable=False,
    )
    signer_type: Mapped[str] = mapped_column(String(8), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT", name="fk_document_signatures_user_id"), nullable=True
    )
    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("admin_users.id", ondelete="RESTRICT", name="fk_document_signatures_admin_id"), nullable=True
    )
    #: The role the signer states, e.g. "Director".
    signer_role: Mapped[str] = mapped_column(String(100), nullable=False)
    authority_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    content_sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    #: /24 (IPv4) or /48 (IPv6), never the full address (C8).
    ip_prefix: Mapped[str | None] = mapped_column(String(50), nullable=True)
    signed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())


#: Columns of a document that never change after it is rendered.
DOCUMENT_FROZEN = ("deal_id", "kind", "side", "term_sheet_id", "template_id", "body", "content_sha256", "terms",
                   "value_minor", "currency")


def document_freeze_sql(dialect: str) -> list[str]:
    """Triggers refusing a change to a rendered document's text, and any
    update or delete of a signature, for schemas built from the models
    (tests). Migration 0042 carries its own copy."""
    if dialect == "sqlite":
        changed = " OR ".join(f"NEW.{c} IS NOT OLD.{c}" for c in DOCUMENT_FROZEN)
        return [
            f"CREATE TRIGGER trg_deal_documents_frozen BEFORE UPDATE ON deal_documents WHEN {changed} "
            "BEGIN SELECT RAISE(ABORT, 'deal_document_frozen'); END",
            "CREATE TRIGGER trg_document_signatures_insert_only BEFORE UPDATE ON document_signatures "
            "BEGIN SELECT RAISE(ABORT, 'signature_insert_only'); END",
        ]
    # json has no equality operator in Postgres: compare its text.
    changed = " OR ".join(
        f"NEW.{c}::text IS DISTINCT FROM OLD.{c}::text" if c == "terms" else f"NEW.{c} IS DISTINCT FROM OLD.{c}"
        for c in DOCUMENT_FROZEN
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


for _dialect in ("sqlite", "postgresql"):
    for _sql in document_freeze_sql(_dialect):
        _table = DocumentSignature.__table__ if "signature" in _sql else DealDocument.__table__
        event.listen(_table, "after_create", DDL(_sql).execute_if(dialect=_dialect))
