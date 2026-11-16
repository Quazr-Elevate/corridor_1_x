"""The admin side of listings: the review queue, approve, reject, and which
certificates buyers may download. No FastAPI imports."""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from pydantic.alias_generators import to_camel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequest, Conflict, NotFound
from app.core.time import utcnow
from app.models.business import Business
from app.models.listing import ProductCertificate
from app.models.product import ListingStatus, Product
from app.modules.admin.service import Actor, clean_reason, record_action
from app.modules.catalog import certificates, service
from app.modules.catalog.lifecycle import transition
from app.modules.catalog.queries import _escape_like, hydrate_businesses
from app.modules.masking import service as masking
from app.modules.catalog.schemas import ProductRead
from app.shared import leakfilter
from app.shared.schemas import CamelModel

S = ListingStatus

QUEUES = ("pending", "all")


class ListingSeller(CamelModel):
    business_id: str
    company_code: str | None = None
    #: The reviewer needs the name to spot a listing that gives it away.
    legal_name: str | None = None
    state: str | None = None
    country: str | None = None
    verified: bool


class RevisionChange(CamelModel):
    """One field of a pending edit: what is live now and what was proposed."""

    field: str
    current: Any = None
    proposed: Any = None


class AdminListingRow(CamelModel):
    id: str
    name: str
    category: str
    status: str
    # "new" — a submitted listing; "revision" — edits to a published one;
    # null — nothing waiting.
    review_kind: str | None = None
    waiting_since: Any = None
    photo: str | None = None
    seller: ListingSeller


class AdminListingList(CamelModel):
    total: int
    items: list[AdminListingRow]


class LeakFlag(CamelModel):
    field: str
    reasons: list[str]


class AdminListingDetail(CamelModel):
    listing: ProductRead
    review_kind: str | None = None
    seller: ListingSeller
    changes: list[RevisionChange] = []
    #: Text the leak filter wants a person to look at, live and proposed.
    leak_flags: list[LeakFlag] = []


def _kind(p: Product) -> str | None:
    if p.status == S.under_review:
        return "new"
    return "revision" if p.pending_revision else None


def _seller(b: Business | None, business_id: uuid.UUID, legal_name: str | None) -> ListingSeller:
    return ListingSeller(
        business_id=str(business_id), company_code=b.company_code if b else None, legal_name=legal_name,
        state=b.state if b else None, country=b.country if b else None, verified=bool(b and b.is_verified),
    )


def _leak_flags(product: Product, legal_name: str | None) -> list[LeakFlag]:
    """What the filter found in the listing's text and in a pending edit,
    plus any mention of the seller's own name."""
    proposed = product.pending_revision or {}
    flags: list[LeakFlag] = []
    for field in service.LEAK_CHECKED_FIELDS:
        texts = [t for t in (getattr(product, field), proposed.get(field)) if isinstance(t, str)]
        reasons: list[str] = []
        for text in texts:
            reasons += [r for r in leakfilter.check(text).reasons if r not in reasons]
            if leakfilter.mentions(text, legal_name) and "names the seller" not in reasons:
                reasons.append("names the seller")
        if reasons:
            flags.append(LeakFlag(field=field, reasons=reasons))
    return flags


def _waiting(p: Product):
    return p.submitted_at if p.status == S.under_review else p.revision_submitted_at


async def list_listings(
    db: AsyncSession, admin: Actor, *, queue: str, status: str | None, q: str | None, limit: int, offset: int
) -> AdminListingList:
    """``queue=pending``: listings waiting for a decision (new submissions and
    edits to published listings), oldest first. ``queue=all``: every listing,
    newest first, optionally one status."""
    stmt = select(Product).where(Product.deleted_at.is_(None))
    if queue == "pending":
        stmt = stmt.where(or_(Product.status == S.under_review, Product.revision_submitted_at.is_not(None)))
        order = (func.coalesce(Product.revision_submitted_at, Product.submitted_at).asc(),)
    else:
        if status:
            if status not in S.ALL:
                raise BadRequest("Unknown listing status.")
            stmt = stmt.where(Product.status == status)
        order = (Product.created_at.desc(),)
    if q and q.strip():
        stmt = stmt.where(Product.name.ilike(f"%{_escape_like(q.strip())}%", escape="\\"))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(await db.scalars(stmt.order_by(*order).offset(offset).limit(limit)))
    sellers = await hydrate_businesses(db, [r.business_id for r in rows])
    names = await masking.names_for_staff(db, admin, list(sellers))
    return AdminListingList(
        total=total,
        items=[
            AdminListingRow(
                id=str(p.id), name=p.name, category=p.category, status=p.status, review_kind=_kind(p),
                waiting_since=_waiting(p), photo=(p.photos or [None])[0],
                seller=_seller(sellers.get(p.business_id), p.business_id, names.get(p.business_id)),
            )
            for p in rows
        ],
    )


async def _listing(db: AsyncSession, product_id: uuid.UUID | None) -> Product:
    product = await db.get(Product, product_id) if product_id else None
    if product is None or product.deleted_at is not None:
        raise NotFound("Listing not found")
    return product


async def listing_detail(db: AsyncSession, admin: Actor, product_id: uuid.UUID | None) -> AdminListingDetail:
    """A listing for review with its seller's name. Stages
    ``identity.unmasked``; the router commits."""
    product = await _listing(db, product_id)
    identity = await masking.unmask_for_staff(db, admin, product.business_id, purpose="listing_review")
    read = await service.read_product(db, product)
    for cert in read.certificates:
        cert.url = f"/admin/listings/{product.id}/certificates/{cert.id}/file"
    live = read.model_dump(by_alias=True)
    changes = [
        RevisionChange(field=field, current=live.get(field), proposed=proposed)
        for field, proposed in (read.pending_revision or {}).items()
    ]
    return AdminListingDetail(
        listing=read, review_kind=_kind(product),
        seller=_seller(await db.get(Business, product.business_id), product.business_id, identity.legal_name),
        changes=changes, leak_flags=_leak_flags(product, identity.legal_name),
    )


async def approve(db: AsyncSession, admin: Actor, product_id: uuid.UUID | None) -> Product:
    """Publish a submitted listing, or apply the edits waiting on a published
    one."""
    product = await _listing(db, product_id)
    now = utcnow()
    if product.status == S.under_review:
        transition(product, S.published, now=now, admin_id=admin.id)
        record_action(db, admin=admin, action="listing.approve", target_type="product", target_id=product.id,
                      details={"businessId": str(product.business_id)})
    elif product.pending_revision:
        revision = dict(product.pending_revision)
        specs = revision.pop("specs", None)
        fields = {
            f: Decimal(v) if f == "capacity_per_month" and v is not None else v for f, v in revision.items()
        }
        for field, value in fields.items():
            setattr(product, field, value)
        if specs is not None:
            await service.replace_specs(db, product, specs)
        product.pending_revision = None
        product.revision_submitted_at = None
        product.revision_rejection_reason = None
        product.reviewed_at = now
        product.reviewed_by = admin.id
        record_action(
            db, admin=admin, action="listing.revision_approve", target_type="product", target_id=product.id,
            details={"businessId": str(product.business_id), "fields": sorted(to_camel(f) for f in product_fields(revision, specs))},
        )
    else:
        raise Conflict("This listing has nothing waiting for review.")
    await db.commit()
    await db.refresh(product)
    return product


def product_fields(revision: dict[str, Any], specs: Any) -> list[str]:
    return [*revision, *(["specs"] if specs is not None else [])]


async def reject(db: AsyncSession, admin: Actor, product_id: uuid.UUID | None, reason: str) -> Product:
    """Reject a submission (the seller fixes and resubmits), or turn down the
    edits waiting on a published listing (the published version stays live).
    A published listing with nothing waiting is taken down."""
    reason = clean_reason(reason)
    product = await _listing(db, product_id)
    now = utcnow()
    if product.pending_revision and product.status in (S.published, S.paused):
        fields = sorted(to_camel(f) for f in product.pending_revision)
        product.pending_revision = None
        product.revision_submitted_at = None
        product.revision_rejection_reason = reason
        product.reviewed_at = now
        product.reviewed_by = admin.id
        action, details = "listing.revision_reject", {"businessId": str(product.business_id), "fields": fields}
    else:
        was = product.status
        transition(product, S.rejected, now=now, admin_id=admin.id, reason=reason)
        action = "listing.reject" if was == S.under_review else "listing.take_down"
        details = {"businessId": str(product.business_id)}
    record_action(db, admin=admin, action=action, target_type="product", target_id=product.id, reason=reason,
                  details=details)
    await db.commit()
    await db.refresh(product)
    return product


async def _certificate(db: AsyncSession, product_id: uuid.UUID | None, certificate_id: uuid.UUID | None):
    product = await _listing(db, product_id)
    return product, await certificates._certificate(db, product.id, certificate_id)


async def set_certificate_visibility(
    db: AsyncSession, admin: Actor, product_id: uuid.UUID | None, certificate_id: uuid.UUID | None, visibility: str
) -> ProductCertificate:
    """Decide whether verified buyers may download this certificate."""
    product, cert = await _certificate(db, product_id, certificate_id)
    cert.visibility = visibility
    cert.visibility_set_by = admin.id
    cert.visibility_set_at = utcnow()
    record_action(
        db, admin=admin, action="listing.certificate_visibility", target_type="product_certificate",
        target_id=cert.id, details={"productId": str(product.id), "visibility": visibility},
    )
    await db.commit()
    await db.refresh(cert)
    return cert


async def open_certificate(
    db: AsyncSession, admin: Actor, product_id: uuid.UUID | None, certificate_id: uuid.UUID | None
) -> tuple[ProductCertificate, bytes]:
    product, cert = await _certificate(db, product_id, certificate_id)
    data = await certificates.read_bytes(cert)
    record_action(
        db, admin=admin, action="listing.certificate_viewed", target_type="product_certificate", target_id=cert.id,
        details={"productId": str(product.id), "businessId": str(product.business_id)},
    )
    await db.commit()
    return cert, data
