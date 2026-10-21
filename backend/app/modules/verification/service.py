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
from app.models.business_document import BusinessDocument
from app.models.user import User
from app.shared.files import safe_filename

# Big enough for a scanned PDF/photo, small enough that a wrong upload
# doesn't choke the server.
MAX_DOC_BYTES = 10 * 1024 * 1024
STORAGE_PREFIX = "verification"


async def upload_doc(
    db: AsyncSession, user: User, *, cert_type: str, filename: str | None, content: bytes
) -> BusinessDocument:
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

    key = f"{STORAGE_PREFIX}/{user.business_id}/{uuid.uuid4().hex}.{ftype.ext}"
    await get_storage().save(content, key, ftype.mime)

    doc = BusinessDocument(
        business_id=user.business_id,
        uploaded_by_user_id=user.id,
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
