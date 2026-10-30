from __future__ import annotations

import uuid
from datetime import datetime

from app.core.crypto import mask
from app.models.business_document import BusinessDocument
from app.models.kyb_document_type import KybDocumentType
from app.shared.schemas import CamelModel


class CountryOut(CamelModel):
    """A country businesses can pick, with its address conventions."""

    code: str
    name: str
    flag: str | None = None
    dial_code: str | None = None
    default_currency: str
    region_label: str
    postal_label: str
    postal_pattern: str | None = None


def country_to_out(c) -> CountryOut:
    return CountryOut(
        code=c.code, name=c.name, flag=c.flag, dial_code=c.dial_code, default_currency=c.default_currency,
        region_label=c.region_label, postal_label=c.postal_label, postal_pattern=c.postal_pattern,
    )


class DocTypeOut(CamelModel):
    """One option of the KYB dropdown (``kyb_document_types``)."""

    id: str
    country: str
    code: str
    name: str
    input_kind: str
    needs_value: bool
    needs_file: bool
    value_pattern: str | None = None
    value_placeholder: str | None = None
    help_text: str | None = None
    is_mandatory: bool
    sort_order: int


def doc_type_to_out(t: KybDocumentType) -> DocTypeOut:
    return DocTypeOut(
        id=str(t.id),
        country=t.country,
        code=t.code,
        name=t.name,
        input_kind=t.input_kind.value,
        needs_value=t.needs_value,
        needs_file=t.needs_file,
        value_pattern=t.value_pattern,
        value_placeholder=t.value_placeholder,
        help_text=t.help_text,
        is_mandatory=t.is_mandatory,
        sort_order=t.sort_order,
    )


class DocOut(CamelModel):
    """A KYB entry as returned to the business's users and to admins.

    The value is **never** included in full — only ``valueMasked``
    (``••••1Z5``); the full number comes from the dedicated reveal call.
    ``certType`` is the display name (the type's name, or the custom name of
    an "Other" entry). ``url`` is an authenticated route to the file (users:
    ``/me/verification-docs/{id}/file``, admins: ``/admin/docs/{id}/file``),
    or null when the entry has no file. There is no public URL for KYB files.
    """

    id: str
    document_type_id: str | None = None
    document_type_code: str | None = None
    is_other: bool
    cert_type: str
    has_value: bool
    value_masked: str | None = None
    has_file: bool
    filename: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    status: str
    rejection_reason: str | None = None
    uploaded_at: datetime
    updated_at: datetime | None = None
    reviewed_at: datetime | None = None
    url: str | None = None


class RevealedValue(CamelModel):
    id: str
    cert_type: str
    value: str


def user_doc_url(doc_id: uuid.UUID) -> str:
    return f"/me/verification-docs/{doc_id}/file"


def admin_doc_url(doc_id: uuid.UUID) -> str:
    return f"/admin/docs/{doc_id}/file"


def doc_to_out(doc: BusinessDocument, *, for_admin: bool = False) -> DocOut:
    url = None
    if doc.has_file:
        url = admin_doc_url(doc.id) if for_admin else user_doc_url(doc.id)
    t = doc.document_type
    return DocOut(
        id=str(doc.id),
        document_type_id=str(doc.document_type_id) if doc.document_type_id else None,
        document_type_code=t.code if t else None,
        is_other=doc.document_type_id is None,
        cert_type=doc.doc_type,
        has_value=doc.has_value,
        value_masked=mask(doc.value_last4),
        has_file=doc.has_file,
        filename=doc.original_filename,
        mime_type=doc.mime_type,
        size_bytes=doc.size_bytes,
        status=doc.status.value,
        rejection_reason=doc.rejection_reason,
        uploaded_at=doc.uploaded_at,
        updated_at=doc.updated_at,
        reviewed_at=doc.reviewed_at,
        url=url,
    )
