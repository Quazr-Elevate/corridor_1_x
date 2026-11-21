"""Listing certificates: COA, test reports, product certificates.

A seller uploads one file per certificate type. It is **internal** until an
admin marks it downloadable; then a verified buyer may fetch it, and each
download is recorded in ``certificate_downloads``.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequest, Conflict, NotFound, PayloadTooLarge, UnsupportedMediaType
from app.core.time import utcnow
from app.integrations.storage import DOCUMENT_TYPES, StorageError, detect, get_storage
from app.models.business import Business
from app.models.listing import ALL_CATEGORIES, CertificateDownload, CertificateType, ProductCertificate
from app.models.product import ListingStatus, Product
from app.models.user import User
from app.modules.catalog import service
from app.modules.catalog.queries import visible_products_select
from app.modules.catalog.schemas import CertificateOut
from app.shared.files import safe_filename
from app.shared.images import strip_metadata

log = logging.getLogger("app.catalog")

MAX_CERTIFICATE_BYTES = 10 * 1024 * 1024
STORAGE_PREFIX = "listing-certificates"


async def _delete_file(key: str) -> None:
    try:
        await get_storage().delete(key)
    except StorageError:
        log.warning("certificate_file_delete_failed key=%s", key)


async def add_certificate(
    db: AsyncSession, user: User, product_id: uuid.UUID | None, type_id: uuid.UUID | None,
    filename: str | None, content: bytes,
) -> CertificateOut:
    """Attach (or replace) the listing's file for one certificate type. A
    replaced file goes back to internal: the admin approved the old one."""
    product = await service.get_own_product(db, user, product_id)
    if product.status == ListingStatus.under_review:
        raise Conflict("This listing is with the reviewer. Withdraw it to change its documents.")
    ctype = await db.get(CertificateType, type_id) if type_id else None
    if ctype is None or not ctype.active or ctype.category not in (product.category, ALL_CATEGORIES):
        raise BadRequest("Choose a document type from this category's list.")
    if not content:
        raise BadRequest("Empty file.")
    if len(content) > MAX_CERTIFICATE_BYTES:
        raise PayloadTooLarge(f"File too large. Max {MAX_CERTIFICATE_BYTES // (1024 * 1024)} MB.")
    ftype = detect(content)
    if ftype is None or ftype not in DOCUMENT_TYPES:
        raise UnsupportedMediaType("Only PDF, JPG, PNG or WEBP files are accepted.")
    content = await strip_metadata(content, ftype)
    key = f"{STORAGE_PREFIX}/{product.business_id}/{uuid.uuid4().hex}.{ftype.ext}"
    await get_storage().save(content, key, ftype.mime)

    existing = await db.scalar(
        select(ProductCertificate).where(
            ProductCertificate.product_id == product.id, ProductCertificate.certificate_type_id == ctype.id
        )
    )
    old_key = existing.storage_key if existing else None
    cert = existing or ProductCertificate(product_id=product.id, certificate_type_id=ctype.id)
    cert.storage_key = key
    cert.original_filename = safe_filename(filename, default=f"certificate.{ftype.ext}")[:300]
    cert.mime_type = ftype.mime
    cert.size_bytes = len(content)
    cert.visibility = "internal"
    cert.visibility_set_by = None
    cert.visibility_set_at = None
    cert.uploaded_by_user_id = user.id
    cert.created_at = utcnow()
    db.add(cert)
    await db.commit()
    await db.refresh(cert)
    if old_key:
        await _delete_file(old_key)
    return service.certificate_out(cert, ctype)


async def delete_certificate(
    db: AsyncSession, user: User, product_id: uuid.UUID | None, certificate_id: uuid.UUID | None
) -> None:
    product = await service.get_own_product(db, user, product_id)
    cert = await _certificate(db, product.id, certificate_id)
    editable = (ListingStatus.draft, ListingStatus.rejected)
    required = await service.required_certificate_ids(db, product.category)
    if cert.certificate_type_id in required and product.status not in editable:
        raise Conflict("This document is required for the category. Upload a replacement instead of removing it.")
    key = cert.storage_key
    await db.delete(cert)
    await db.commit()
    await _delete_file(key)


async def _certificate(db: AsyncSession, product_id: uuid.UUID, certificate_id: uuid.UUID | None) -> ProductCertificate:
    cert = (
        await db.scalar(
            select(ProductCertificate).where(
                ProductCertificate.id == certificate_id, ProductCertificate.product_id == product_id
            )
        )
        if certificate_id
        else None
    )
    if cert is None:
        raise NotFound("Document not found")
    return cert


async def read_bytes(cert: ProductCertificate) -> bytes:
    try:
        return await get_storage().open(cert.storage_key)
    except StorageError:
        raise NotFound("Document file is missing") from None


_EXT_BY_MIME = {t.mime: t.ext for t in DOCUMENT_TYPES}


async def buyer_filename(db: AsyncSession, cert: ProductCertificate, product: Product) -> str:
    """``IN-482913-coa.pdf``: the seller's code and the document type. The
    seller's own file name often carries the company's name (A-056)."""
    seller = await db.get(Business, product.business_id)
    ctype = await db.get(CertificateType, cert.certificate_type_id)
    code = (seller.company_code if seller else None) or "seller"
    kind = ctype.code if ctype else "document"
    return f"{code}-{kind}.{_EXT_BY_MIME.get(cert.mime_type, 'bin')}"


async def open_certificate(
    db: AsyncSession, user: User, product_id: uuid.UUID | None, certificate_id: uuid.UUID | None
) -> tuple[str, bytes]:
    """The download name and the file, for the listing's own business, or
    for a verified buyer when the listing is in the market and an admin
    approved the download. Anyone else gets 404, so the route doesn't confirm
    that a document exists."""
    product = await db.get(Product, product_id) if product_id else None
    if product is None or product.deleted_at is not None:
        raise NotFound("Document not found")
    if product.business_id == user.business_id:
        cert = await _certificate(db, product.id, certificate_id)
        return cert.original_filename, await read_bytes(cert)

    visible = await db.scalar(visible_products_select().where(Product.id == product.id))
    if visible is None or not user.business.is_verified:
        raise NotFound("Document not found")
    cert = await _certificate(db, product.id, certificate_id)
    if cert.visibility != "downloadable":
        raise NotFound("Document not found")
    data = await read_bytes(cert)
    db.add(
        CertificateDownload(
            certificate_id=cert.id, product_id=product.id, buyer_business_id=user.business_id, user_id=user.id,
            downloaded_at=utcnow(),
        )
    )
    await db.commit()
    log.info("certificate_downloaded certificate_id=%s buyer_business_id=%s", cert.id, user.business_id)
    return await buyer_filename(db, cert, product), data
