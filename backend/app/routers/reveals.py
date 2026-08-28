"""Contact reveal — the funnel's payoff.

`POST /products/{id}/contact-reveal` is the only place seller contact
info leaves the backend. Gated by:

  1. Caller must be signed in (session cookie or X-User-Id header).
  2. Caller's `users.status` must be `verified`.
  3. Target product's seller must also be verified (public-catalog rule).
  4. Rate limit: 20 successful reveals per buyer per hour.

Idempotent: the (buyer, product) UNIQUE means a second reveal of the
same product is free and returns the same card. The audit row is created
on first reveal only.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models.business_profile import BusinessProfile
from app.models.contact_reveal import ContactReveal
from app.models.product import Product
from app.models.profile import Profile
from app.models.user import User, UserStatus
from app.queries import primary_mobile, visible_users_clause
from app.schemas.reveal import RevealedContact

router = APIRouter(prefix="/products", tags=["reveals"])

# Buyers get 20 reveals/hour. Legitimate use is 1-3 per session; anything
# above signals scraping and hits this cap.
REVEAL_WINDOW_SEC = 60 * 60
REVEAL_MAX_PER_WINDOW = 20


async def _check_buyer_gate(user: User) -> None:
    """Buyer must be verified to reveal ANY contact — this is the whole
    point of the platform. Soft-deleted users can't even reach this
    handler (deps.get_current_user filters them out)."""
    if user.status != UserStatus.verified:
        raise HTTPException(
            status_code=403,
            detail=(
                "Complete your profile verification before revealing seller "
                "contact details."
            ),
        )


async def _check_reveal_rate(user: User, db: AsyncSession) -> None:
    now = datetime.now(tz=timezone.utc)
    window_start = now.replace(microsecond=0).timestamp() - REVEAL_WINDOW_SEC
    recent = await db.scalar(
        select(func.count(ContactReveal.id)).where(
            ContactReveal.buyer_id == user.id,
            ContactReveal.revealed_at
            >= datetime.fromtimestamp(window_start, tz=timezone.utc),
        )
    ) or 0
    if recent >= REVEAL_MAX_PER_WINDOW:
        raise HTTPException(
            status_code=429,
            detail=(
                f"You've hit the reveal limit ({REVEAL_MAX_PER_WINDOW}/hour). "
                "Come back shortly."
            ),
            headers={"Retry-After": str(REVEAL_WINDOW_SEC)},
        )


def _to_dto(
    seller_id: uuid.UUID,
    profile: Profile | None,
    business: BusinessProfile | None,
    mobile: str | None,
    revealed_at: datetime,
) -> RevealedContact:
    return RevealedContact(
        seller_id=str(seller_id),
        full_name=profile.full_name if profile else None,
        company_name=business.company_name if business else None,
        business_type=business.business_type if business else None,
        mobile=mobile,
        email=profile.email if profile else None,
        business_email=profile.business_email if profile else None,
        address_line=profile.address_line if profile else None,
        city=profile.city if profile else None,
        state=profile.state if profile else None,
        pincode=profile.pincode if profile else None,
        country=profile.country if profile else None,
        website_url=profile.website_url if profile else None,
        revealed_at=revealed_at,
    )


@router.post(
    "/{product_id}/contact-reveal",
    response_model=RevealedContact,
    response_model_by_alias=True,
)
async def reveal_contact(
    product_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RevealedContact:
    try:
        pid = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Product not found") from None

    await _check_buyer_gate(user)

    # Product must exist and belong to a visible (verified, non-deleted) seller.
    stmt = (
        select(Product)
        .join(User, User.id == Product.user_id)
        .where(Product.id == pid, visible_users_clause())
    )
    product = await db.scalar(stmt)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    seller_id = product.user_id
    # A user cannot "reveal" their own listing — surface a clear message
    # so the UI can hide the reveal button in this case.
    if seller_id == user.id:
        raise HTTPException(
            status_code=400,
            detail="This is your own listing — nothing to reveal.",
        )

    # Idempotent: return the existing row if the buyer already unlocked.
    existing = await db.scalar(
        select(ContactReveal).where(
            ContactReveal.buyer_id == user.id, ContactReveal.product_id == pid
        )
    )
    revealed_at: datetime
    if existing is None:
        # New reveal — rate-check before creating the row so a burst of
        # duplicate requests doesn't consume the quota.
        await _check_reveal_rate(user, db)
        reveal = ContactReveal(
            buyer_id=user.id, seller_id=seller_id, product_id=pid
        )
        db.add(reveal)
        await db.commit()
        await db.refresh(reveal)
        revealed_at = reveal.revealed_at
    else:
        revealed_at = existing.revealed_at

    profile = await db.scalar(select(Profile).where(Profile.user_id == seller_id))
    business = await db.scalar(
        select(BusinessProfile).where(BusinessProfile.user_id == seller_id)
    )
    mobile = await primary_mobile(db, seller_id)
    return _to_dto(seller_id, profile, business, mobile, revealed_at)
