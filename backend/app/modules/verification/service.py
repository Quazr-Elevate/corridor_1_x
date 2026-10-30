"""KYB document storage rules (upload / list / read / delete).

Documents belong to a business: any user of that business (and admins)
may list / download / delete them.
"""
from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequest, NotFound, PayloadTooLarge, UnsupportedMediaType
from app.integrations.storage import DOCUMENT_TYPES, StorageError, detect, get_storage
from app.models.business import Business
from app.models.business_document import BusinessDocument
from app.models.business_document_requirement import BusinessDocumentRequirement
from app.models.user import User
from app.modules.verification.schemas import (
    DocRequirementsResponse,
    DocSlot,
    doc_to_out,
)
from app.shared.files import safe_filename

# Big enough for a scanned PDF/photo, small enough that a wrong upload
# doesn't choke the server.
MAX_DOC_BYTES = 10 * 1024 * 1024
STORAGE_PREFIX = "verification"


async def upload_doc(
    db: AsyncSession,
    user: User,
    *,
    cert_type: str,
    filename: str | None,
    content: bytes,
    required_doc_type_id: uuid.UUID | None = None,
) -> BusinessDocument:
    """Upload a KYB document. When ``required_doc_type_id`` is passed, the
    upload is linked to that catalog row — the row must be active, belong
    to the user's country, and nothing else of theirs may be currently
    filling the same slot (user replaces by deleting the old one first)."""
    cert_type = cert_type.strip()
    if not cert_type:
        raise BadRequest("Pick a certificate type before uploading.")
    if len(cert_type) > 150:
        raise BadRequest("Certificate type is too long (150 chars max).")
    if not content:
        raise BadRequest("Empty file.")
    if len(content) > MAX_DOC_BYTES:
        raise PayloadTooLarge(f"File too large. Max {MAX_DOC_BYTES // (1024 * 1024)} MB.")

    ftype = detect(content)
    if ftype is None or ftype not in DOCUMENT_TYPES:
        raise UnsupportedMediaType("Only PDF, JPG, PNG or WEBP files are accepted.")

    if required_doc_type_id is not None:
        req = await db.get(BusinessDocumentRequirement, required_doc_type_id)
        business = await db.get(Business, user.business_id)
        if req is None or not req.is_active:
            raise BadRequest("That document type is not currently requested for your country.")
        if business is None or req.country_code != business.country:
            raise BadRequest("That document type is for a different country.")

    key = f"{STORAGE_PREFIX}/{user.business_id}/{uuid.uuid4().hex}.{ftype.ext}"
    await get_storage().save(content, key, ftype.mime)

    # Replace: a slot holds at most one upload. If one already exists
    # for this (business, requirement), drop its file and row before
    # saving the replacement. Keeps the Documents tab linear and makes
    # "the current cert" unambiguous for admin review.
    if required_doc_type_id is not None:
        existing = list(
            await db.scalars(
                select(BusinessDocument)
                .where(BusinessDocument.business_id == user.business_id)
                .where(BusinessDocument.required_doc_type_id == required_doc_type_id)
            )
        )
        for old in existing:
            try:
                await get_storage().delete(old.storage_key)
            except StorageError:
                pass  # malformed / already gone — drop the row anyway
            await db.delete(old)

    doc = BusinessDocument(
        business_id=user.business_id,
        uploaded_by_user_id=user.id,
        required_doc_type_id=required_doc_type_id,
        doc_type=cert_type,
        original_filename=safe_filename(filename, default=f"document.{ftype.ext}")[:300],
        storage_key=key,
        mime_type=ftype.mime,
        size_bytes=len(content),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def list_doc_requirements(db: AsyncSession, user: User) -> DocRequirementsResponse:
    """Build the Documents tab payload: required / optional slots for the
    user's country, plus any custom (non-slot) uploads they've made."""
    business = await db.get(Business, user.business_id)
    country = (business.country if business else "").upper()

    reqs = list(
        await db.scalars(
            select(BusinessDocumentRequirement)
            .where(BusinessDocumentRequirement.country_code == country)
            .where(BusinessDocumentRequirement.is_active.is_(True))
            .order_by(
                BusinessDocumentRequirement.is_mandatory.desc(),
                BusinessDocumentRequirement.display_name,
            )
        )
    )
    docs = list(await list_docs(db, user.business_id))

    # Latest upload per requirement slot.
    by_req: dict[uuid.UUID, BusinessDocument] = {}
    for d in docs:  # already ordered newest-first
        if d.required_doc_type_id is not None and d.required_doc_type_id not in by_req:
            by_req[d.required_doc_type_id] = d
    custom = [d for d in docs if d.required_doc_type_id is None]

    required_out: list[DocSlot] = []
    optional_out: list[DocSlot] = []
    for r in reqs:
        upload = by_req.get(r.id)
        slot = DocSlot(
            requirement_id=str(r.id),
            slug=r.slug,
            display_name=r.display_name,
            description=r.description,
            help_url=r.help_url,
            is_mandatory=r.is_mandatory,
            upload=doc_to_out(upload, requirement=r) if upload else None,
        )
        (required_out if r.is_mandatory else optional_out).append(slot)

    return DocRequirementsResponse(
        country_code=country,
        required=required_out,
        optional=optional_out,
        custom_uploads=[doc_to_out(d) for d in custom],
    )


async def list_docs(db: AsyncSession, business_id: uuid.UUID) -> Sequence[BusinessDocument]:
    return list(
        await db.scalars(
            select(BusinessDocument)
            .where(BusinessDocument.business_id == business_id)
            .order_by(BusinessDocument.uploaded_at.desc())
        )
    )


async def get_doc(
    db: AsyncSession, doc_id: uuid.UUID | None, *, business_id: uuid.UUID | None = None
) -> BusinessDocument:
    """Fetch a doc; with ``business_id`` a doc of another business is
    reported as missing (no existence leak)."""
    doc = await db.get(BusinessDocument, doc_id) if doc_id else None
    if doc is None or (business_id is not None and doc.business_id != business_id):
        raise NotFound("Document not found")
    return doc


async def read_doc_bytes(doc: BusinessDocument) -> bytes:
    try:
        return await get_storage().open(doc.storage_key)
    except StorageError:
        raise NotFound("Document file is missing") from None


async def delete_doc(db: AsyncSession, user: User, doc_id: uuid.UUID | None) -> None:
    doc = await get_doc(db, doc_id, business_id=user.business_id)
    try:
        await get_storage().delete(doc.storage_key)
    except StorageError:
        pass  # malformed legacy key — still drop the row
    await db.delete(doc)
    await db.commit()
