from __future__ import annotations

import uuid
from datetime import datetime

from app.models.business_document import BusinessDocument
from app.models.business_document_requirement import BusinessDocumentRequirement
from app.shared.schemas import CamelModel


class DocOut(CamelModel):
    """A KYB document as returned to the business's users and to admins.

    Wire names ``certType`` / ``filename`` are kept for the frontend
    (columns ``doc_type`` / ``original_filename``). ``url`` is a relative,
    authenticated route — the business's users get
    ``/me/verification-docs/{id}/file`` and admins
    ``/admin/docs/{id}/file``. There is no public URL for KYB files.

    ``requiredDocTypeId`` tells the admin UI (and the business profile)
    whether this upload fills a country-mandated slot (business
    certificate) or is a free-form custom upload (other certificate).
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
    required_doc_type_id: str | None = None
    #: Admin-defined display name for the catalog slot this upload fills
    #: (e.g. "Business registration certificate"). Null for custom
    #: ("other") uploads. Set alongside ``required_doc_type_id``.
    requirement_display_name: str | None = None
    #: Catalog slug for the slot (``business_registration``). Null for
    #: custom uploads. Lets admin UI build stable keys like
    #: ``doc:business_registration`` without depending on the trader's
    #: free-text ``cert_type``.
    requirement_slug: str | None = None


def user_doc_url(doc_id: uuid.UUID) -> str:
    return f"/me/verification-docs/{doc_id}/file"


def admin_doc_url(doc_id: uuid.UUID) -> str:
    return f"/admin/docs/{doc_id}/file"


def doc_to_out(
    doc: BusinessDocument,
    *,
    for_admin: bool = False,
    requirement: BusinessDocumentRequirement | None = None,
) -> DocOut:
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
        required_doc_type_id=str(doc.required_doc_type_id) if doc.required_doc_type_id else None,
        requirement_display_name=requirement.display_name if requirement else None,
        requirement_slug=requirement.slug if requirement else None,
    )


class DocSlot(CamelModel):
    """One row of the Documents tab — either a country-mandated slot (with
    optional ``upload`` describing the user's current fill) or a custom
    uploaded doc (``requirement_id`` None)."""

    requirement_id: str | None
    slug: str | None
    display_name: str
    description: str | None = None
    help_url: str | None = None
    is_mandatory: bool
    upload: DocOut | None = None


class DocRequirementsResponse(CamelModel):
    """GET /me/doc-requirements response.

    ``required`` groups the mandatory, un-retired slots for the user's
    country; ``optional`` holds the non-mandatory ones seeded for the same
    country. ``custom_uploads`` collects any upload with no
    ``required_doc_type_id`` — doc types the user chose freely.
    """

    country_code: str
    required: list[DocSlot]
    optional: list[DocSlot]
    custom_uploads: list[DocOut]
