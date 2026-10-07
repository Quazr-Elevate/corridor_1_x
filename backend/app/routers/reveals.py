"""Contact reveal — the funnel's payoff.

`POST /products/{id}/contact-reveal` is the only place seller contact
info leaves the backend. Gated by:

  1. Caller must be signed in (session cookie or X-User-Id header).
  2. Caller's `users.status` must be `verified`.
  3. Target product's seller must also be verified.
  4. Rate limit: 20 successful reveals per buyer per hour.
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
from app.queries import visible_users_clause
from app.schemas.reveal import RevealedContact

router = APIRouter(prefix="/products", tags=["reveals"])

REVEAL_WINDOW_SEC = 60 * 60
REVEAL_MAX_PER_WINDOW = 20


async def _check_buyer_gate(user: User) -> None:
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
    seller: User,
    profile: Profile | None,
    business: BusinessProfile | None,
    revealed_at: datetime,
) -> RevealedContact:
    return RevealedContact(
        seller_id=str(seller.id),
        full_name=profile.full_name if profile else None,
        business_name=seller.business_name,
        business_type=business.business_type if business else None,
        email=seller.email,
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

    stmt = (
        select(Product)
        .join(User, User.id == Product.user_id)
        .where(Product.id == pid, visible_users_clause())
    )
    product = await db.scalar(stmt)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    seller_id = product.user_id
    if seller_id == user.id:
        raise HTTPException(
            status_code=400,
            detail="This is your own listing — nothing to reveal.",
        )

    existing = await db.scalar(
        select(ContactReveal).where(
            ContactReveal.buyer_id == user.id, ContactReveal.product_id == pid
        )
    )
    revealed_at: datetime
    if existing is None:
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

    seller = await db.get(User, seller_id)
    assert seller is not None  # guarded by visible_users_clause above
    profile = await db.scalar(select(Profile).where(Profile.user_id == seller_id))
    business = await db.scalar(
        select(BusinessProfile).where(BusinessProfile.user_id == seller_id)
    )
    return _to_dto(seller, profile, business, revealed_at)
