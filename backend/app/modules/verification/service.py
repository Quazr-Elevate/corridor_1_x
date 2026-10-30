"""KYB entries of a business (the "Business verification" section).

One entry = a document type (from the admin's list for the business's
country, or "Other" with a custom name) + a value and/or a file:

* values are validated against the type's pattern, then stored encrypted
  (:mod:`app.core.crypto`) with a keyed hash (duplicate checks) and a masked
  hint — the plain value never reaches the database or the logs;
* files are sniffed (PDF/JPEG/PNG/WEBP, ≤ 10 MB) and kept in private storage;
* every add / change puts the entry back to ``pending`` for admin review.

Entries belong to a business: any user of that business may list, change,
reveal and delete them; an entry of another business is reported as
missing (no existence leak). Aadhaar is never accepted.
"""
from __future__ import annotations

import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.core.errors import BadRequest, Conflict, NotFound, PayloadTooLarge, UnsupportedMediaType
from app.integrations.storage import DOCUMENT_TYPES, StorageError, detect, get_storage
from app.models.business import Business
from app.models.business_document import BusinessDocument, DocStatus
from app.models.kyb_document_type import KybDocumentType
from app.models.user import User
from app.modules.verification.rules import reopen_review
from app.shared.files import safe_filename

# Big enough for a scanned PDF/photo, small enough that a wrong upload
# doesn't choke the server.
MAX_DOC_BYTES = 10 * 1024 * 1024
MAX_VALUE_LEN = 100
STORAGE_PREFIX = "verification"
VALUE_TAKEN = "This {name} is already registered to another business on Corridor One X."
_AADHAAR = re.compile(r"aadh?aa?r", re.IGNORECASE)
NO_AADHAAR = "Aadhaar can't be submitted on Corridor One X. Use your business documents instead."


@dataclass
class EntryInput:
    """Parsed form fields of an add / change request. ``None`` = not sent."""

    document_type_id: uuid.UUID | None = None
    custom_name: str | None = None
    value: str | None = None
    filename: str | None = None
    content: bytes | None = None
    remove_value: bool = False
    remove_file: bool = False


# ── Document types (dropdown) ────────────────────────────────────────


async def list_types(db: AsyncSession, country: str) -> list[KybDocumentType]:
    return list(
        await db.scalars(
            select(KybDocumentType)
            .where(KybDocumentType.country == country.upper(), KybDocumentType.active.is_(True))
            .order_by(KybDocumentType.sort_order, KybDocumentType.name)
        )
    )


async def _type_for_business(db: AsyncSession, type_id: uuid.UUID, country: str) -> KybDocumentType:
    t = await db.get(KybDocumentType, type_id)
    if t is None or not t.active:
        raise BadRequest("Unknown document type. Pick one from the list or choose Other.")
    if t.country != country:
        raise BadRequest(f"{t.name} is not a document for your business's country. Update the country first.")
    return t


# ── Validation helpers ───────────────────────────────────────────────


def _clean_value(raw: str, t: KybDocumentType | None, name: str) -> str:
    value = crypto.normalize_value(raw)
    if not value:
        raise BadRequest(f"Enter the {name} number.")
    if len(value) > MAX_VALUE_LEN:
        raise BadRequest(f"{name} is too long ({MAX_VALUE_LEN} characters max).")
    if len(value) < 4:
        raise BadRequest(f"{name} looks too short.")
    if t is not None and t.value_pattern and not re.fullmatch(t.value_pattern, value):
        hint = f" Expected format: {t.value_placeholder}." if t.value_placeholder else ""
        raise BadRequest(f"That doesn't look like a valid {t.name}.{hint}")
    return value


def _clean_custom_name(raw: str | None) -> str:
    name = " ".join((raw or "").split())
    if len(name) < 2:
        raise BadRequest("Enter a name for this document.")
    if len(name) > 150:
        raise BadRequest("Document name is too long (150 characters max).")
    if _AADHAAR.search(name):
        raise BadRequest(NO_AADHAAR)
    return name


async def _store_file(business_id: uuid.UUID, filename: str | None, content: bytes) -> dict:
    if not content:
        raise BadRequest("Empty file.")
    if len(content) > MAX_DOC_BYTES:
        raise PayloadTooLarge(f"File too large. Max {MAX_DOC_BYTES // (1024 * 1024)} MB.")
    ftype = detect(content)
    if ftype is None or ftype not in DOCUMENT_TYPES:
        raise UnsupportedMediaType("Only PDF, JPG, PNG or WEBP files are accepted.")
    key = f"{STORAGE_PREFIX}/{business_id}/{uuid.uuid4().hex}.{ftype.ext}"
    await get_storage().save(content, key, ftype.mime)
    return {
        "original_filename": safe_filename(filename, default=f"document.{ftype.ext}")[:300],
        "storage_key": key,
        "mime_type": ftype.mime,
        "size_bytes": len(content),
    }


async def _delete_file(key: str | None) -> None:
    if not key:
        return
    try:
        await get_storage().delete(key)
    except StorageError:
        pass  # already gone / malformed legacy key


def _set_value(doc: BusinessDocument, value: str, t: KybDocumentType | None) -> None:
    ct, version = crypto.encrypt(value)
    doc.value_encrypted = ct
    doc.value_key_version = version
    doc.value_hash = crypto.value_hash(value, scope=str(t.id) if t else "other")
    doc.value_last4 = crypto.last4(value)
    doc.value_unique = bool(t and t.is_unique)


def _clear_value(doc: BusinessDocument) -> None:
    doc.value_encrypted = doc.value_key_version = doc.value_hash = doc.value_last4 = None
    doc.value_unique = False


def _set_file(doc: BusinessDocument, meta: dict | None) -> None:
    for col in ("original_filename", "storage_key", "mime_type", "size_bytes"):
        setattr(doc, col, meta[col] if meta else None)


async def _ensure_value_free(db: AsyncSession, doc: BusinessDocument, t: KybDocumentType | None) -> None:
    """Friendly pre-check; ``uq_business_documents_unique_value`` is the
    real guard against races."""
    if not doc.value_unique or t is None:
        return
    other = await db.scalar(
        select(BusinessDocument.id).where(
            BusinessDocument.document_type_id == t.id,
            BusinessDocument.value_hash == doc.value_hash,
            BusinessDocument.business_id != doc.business_id,
            BusinessDocument.status != DocStatus.rejected,
            BusinessDocument.value_unique.is_(True),
        )
    )
    if other is not None:
        raise Conflict(VALUE_TAKEN.format(name=t.name))


def _check_parts(doc: BusinessDocument, t: KybDocumentType | None) -> None:
    name = t.name if t else doc.doc_type
    if t is not None and t.needs_value and not doc.has_value:
        raise BadRequest(f"Enter the {name} number.")
    if t is not None and t.needs_file and not doc.has_file:
        raise BadRequest(f"Upload a copy of the {name}.")
    if not doc.has_value and not doc.has_file:
        raise BadRequest("Enter the number or upload the document.")


async def _commit(db: AsyncSession, doc: BusinessDocument, t: KybDocumentType | None) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        msg = str(exc.orig)
        if "unique_value" in msg or "value_hash" in msg:
            raise Conflict(VALUE_TAKEN.format(name=t.name if t else "number")) from None
        if "business_type" in msg or "document_type_id" in msg:
            raise Conflict(f"You already added {t.name if t else 'this document'} — edit that entry instead.") from None
        raise
    await db.refresh(doc)


# ── Entries ──────────────────────────────────────────────────────────


async def add_entry(db: AsyncSession, user: User, data: EntryInput) -> BusinessDocument:
    business = user.business
    t = await _type_for_business(db, data.document_type_id, business.country) if data.document_type_id else None
    if t is None:
        name = _clean_custom_name(data.custom_name)
    else:
        name = t.name
        existing = await db.scalar(
            select(BusinessDocument.id).where(
                BusinessDocument.business_id == business.id, BusinessDocument.document_type_id == t.id
            )
        )
        if existing is not None:
            raise Conflict(f"You already added {t.name} — edit that entry instead.")

    doc = BusinessDocument(
        business_id=business.id, uploaded_by_user_id=user.id, document_type_id=t.id if t else None, doc_type=name
    )
    doc.document_type = t
    if data.value is not None and data.value.strip():
        _set_value(doc, _clean_value(data.value, t, name), t)
    if data.content is not None:
        meta = await _store_file(business.id, data.filename, data.content)
        _set_file(doc, meta)
    try:
        _check_parts(doc, t)
        await _ensure_value_free(db, doc, t)
        db.add(doc)
        if t is not None and t.is_mandatory:
            reopen_review(business)
        await _commit(db, doc, t)
    except Exception:
        await _delete_file(doc.storage_key)
        raise
    return doc


async def update_entry(db: AsyncSession, user: User, doc_id: uuid.UUID | None, data: EntryInput) -> BusinessDocument:
    """Change the value / file (or the custom name of an "Other" entry).
    Any change sends the entry back to ``pending``."""
    doc = await get_doc(db, doc_id, business_id=user.business_id)
    t = doc.document_type
    old_file = doc.storage_key
    new_file: str | None = None
    changed = False

    if data.custom_name is not None:
        if t is not None:
            raise BadRequest("Only entries added as Other can be renamed.")
        doc.doc_type = _clean_custom_name(data.custom_name)
        changed = True
    if data.remove_value:
        _clear_value(doc)
        changed = True
    elif data.value is not None and data.value.strip():
        _set_value(doc, _clean_value(data.value, t, doc.doc_type), t)
        changed = True
    if data.content is not None:
        meta = await _store_file(doc.business_id, data.filename, data.content)
        new_file = meta["storage_key"]
        _set_file(doc, meta)
        changed = True
    elif data.remove_file:
        _set_file(doc, None)
        changed = True
    if not changed:
        raise BadRequest("Nothing to change.")

    try:
        _check_parts(doc, t)
        await _ensure_value_free(db, doc, t)
        doc.status = DocStatus.pending
        doc.rejection_reason = None
        doc.reviewed_at = None
        doc.reviewed_by = None
        if t is not None and t.is_mandatory:
            await _reopen(db, doc.business_id)
        await _commit(db, doc, t)
    except Exception:
        await db.rollback()
        await _delete_file(new_file)
        raise
    if old_file and old_file != doc.storage_key:
        await _delete_file(old_file)
    return doc


async def list_docs(db: AsyncSession, business_id: uuid.UUID) -> Sequence[BusinessDocument]:
    return list(
        await db.scalars(
            select(BusinessDocument)
            .where(BusinessDocument.business_id == business_id)
            .order_by(BusinessDocument.uploaded_at.asc())
        )
    )


async def get_doc(
    db: AsyncSession, doc_id: uuid.UUID | None, *, business_id: uuid.UUID | None = None
) -> BusinessDocument:
    """Fetch an entry; with ``business_id`` an entry of another business is
    reported as missing (no existence leak)."""
    doc = await db.get(BusinessDocument, doc_id) if doc_id else None
    if doc is None or (business_id is not None and doc.business_id != business_id):
        raise NotFound("Document not found")
    return doc


def reveal_value(doc: BusinessDocument) -> str:
    if not doc.has_value:
        raise NotFound("This entry has no number.")
    try:
        return crypto.decrypt(doc.value_encrypted, doc.value_key_version)
    except crypto.DecryptionError:
        raise NotFound("This number can't be read. Please enter it again.") from None


async def read_doc_bytes(doc: BusinessDocument) -> bytes:
    if not doc.has_file:
        raise NotFound("This entry has no file.")
    try:
        return await get_storage().open(doc.storage_key)
    except StorageError:
        raise NotFound("Document file is missing") from None


async def _reopen(db: AsyncSession, business_id: uuid.UUID) -> None:
    business = await db.get(Business, business_id)
    if business is not None:
        reopen_review(business)


async def delete_doc(db: AsyncSession, user: User, doc_id: uuid.UUID | None) -> None:
    doc = await get_doc(db, doc_id, business_id=user.business_id)
    key = doc.storage_key
    if doc.document_type is not None and doc.document_type.is_mandatory:
        await _reopen(db, doc.business_id)
    await db.delete(doc)
    await db.commit()
    await _delete_file(key)
