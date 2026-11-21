"""/admin/listings/* — the listing review queue and decisions.

Approving publishes a submitted listing, or applies the edits waiting on a
published one. Rejecting needs a reason; the seller sees it as written.
Every decision is written to ``admin_actions``."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query, Response

from app.core.security import parse_uuid
from app.modules.admin.deps import CanReviewListings
from app.modules.admin.permissions import Perm
from app.modules.auth.deps import DbSession
from app.modules.catalog import review
from app.modules.catalog.review import AdminListingDetail, AdminListingList
from app.shared.files import file_response
from app.shared.schemas import CamelModel, RequestModel, text

router = APIRouter(prefix="/listings")


class ListingApproveIn(RequestModel):
    override_reason: text(500, 10) | None = None  # type: ignore[valid-type]


class ListingRejectIn(RequestModel):
    reason: text(500, 1)  # type: ignore[valid-type]


class CertificateVisibilityIn(RequestModel):
    visibility: Literal["internal", "downloadable"]
    #: Required for "downloadable": the reviewer opened the file and it shows no name, logo or address.
    checked_no_identity: bool = False


class ListingStatusChanged(CamelModel):
    id: str
    status: str
    # True while edits to a published listing still wait for a decision.
    has_pending_revision: bool


class CertificateVisibilityChanged(CamelModel):
    id: str
    visibility: str


def _changed(product) -> ListingStatusChanged:
    return ListingStatusChanged(
        id=str(product.id), status=product.status, has_pending_revision=bool(product.pending_revision)
    )


@router.get("", response_model=AdminListingList, response_model_by_alias=True)
async def list_listings(
    admin: CanReviewListings,
    db: DbSession,
    queue: Literal["pending", "all"] = Query("pending"),
    status: str | None = Query(None, max_length=20),
    q: str | None = Query(None, max_length=200),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> AdminListingList:
    return await review.list_listings(db, admin, queue=queue, status=status, q=q, limit=limit, offset=offset)


@router.get("/{listing_id}", response_model=AdminListingDetail, response_model_by_alias=True)
async def listing_detail(listing_id: str, admin: CanReviewListings, db: DbSession) -> AdminListingDetail:
    """A listing and its seller's name (audited as ``identity.unmasked``)."""
    detail = await review.listing_detail(db, admin, parse_uuid(listing_id))
    await db.commit()
    return detail


@router.post("/{listing_id}/approve", response_model=ListingStatusChanged, response_model_by_alias=True)
async def approve_listing(
    listing_id: str, admin: CanReviewListings, db: DbSession, payload: ListingApproveIn | None = None
) -> ListingStatusChanged:
    """No body for a clean listing. One the leak filter flagged needs
    ``overrideReason`` and the ``listings.override`` permission."""
    return _changed(await review.approve(
        db, admin, parse_uuid(listing_id),
        override_reason=payload.override_reason if payload else None,
        may_override=Perm.listings_override in admin.permissions,
    ))


@router.post("/{listing_id}/reject", response_model=ListingStatusChanged, response_model_by_alias=True)
async def reject_listing(
    listing_id: str, payload: ListingRejectIn, admin: CanReviewListings, db: DbSession
) -> ListingStatusChanged:
    return _changed(await review.reject(db, admin, parse_uuid(listing_id), payload.reason))


@router.post(
    "/{listing_id}/certificates/{certificate_id}/visibility",
    response_model=CertificateVisibilityChanged,
    response_model_by_alias=True,
)
async def set_certificate_visibility(
    listing_id: str, certificate_id: str, payload: CertificateVisibilityIn, admin: CanReviewListings, db: DbSession
) -> CertificateVisibilityChanged:
    cert = await review.set_certificate_visibility(
        db, admin, parse_uuid(listing_id), parse_uuid(certificate_id), payload.visibility,
        checked_no_identity=payload.checked_no_identity,
    )
    return CertificateVisibilityChanged(id=str(cert.id), visibility=cert.visibility)


@router.get("/{listing_id}/certificates/{certificate_id}/file")
async def open_certificate(listing_id: str, certificate_id: str, admin: CanReviewListings, db: DbSession) -> Response:
    """The certificate file (audited as ``listing.certificate_viewed``)."""
    cert, data = await review.open_certificate(db, admin, parse_uuid(listing_id), parse_uuid(certificate_id))
    return file_response(data, filename=cert.original_filename, cache_control="private, no-store")
