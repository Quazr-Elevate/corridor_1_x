from __future__ import annotations

import uuid
from datetime import datetime

from app.models.business_document import BusinessDocument
from app.shared.schemas import CamelModel


class DocOut(CamelModel):
    """A KYB document as returned to the business's users and to admins.

    Wire names ``certType`` / ``filename`` are kept for the frontend
    (columns ``doc_type`` / ``original_filename``). ``url`` is a relative,
    authenticated route — the business's users get
    ``/me/verification-docs/{id}/file`` and admins
    ``/admin/docs/{id}/file``. There is no public URL for KYB files.
    """

    id: str
    cert_type: str
    filename: str
    mime_type: str
    size_bytes: int
    status: str
    rejection_reason: str | None = None
    uploaded_at: datetime
    reviewed_at: datetime | None = None
    url: str


def user_doc_url(doc_id: uuid.UUID) -> str:
    return f"/me/verification-docs/{doc_id}/file"


def admin_doc_url(doc_id: uuid.UUID) -> str:
    return f"/admin/docs/{doc_id}/file"


def doc_to_out(doc: BusinessDocument, *, for_admin: bool = False) -> DocOut:
    return DocOut(
        id=str(doc.id),
        cert_type=doc.doc_type,
        filename=doc.original_filename,
        mime_type=doc.mime_type,
        size_bytes=doc.size_bytes,
        status=doc.status.value,
        rejection_reason=doc.rejection_reason,
        uploaded_at=doc.uploaded_at,
        reviewed_at=doc.reviewed_at,
        url=admin_doc_url(doc.id) if for_admin else user_doc_url(doc.id),
    )
