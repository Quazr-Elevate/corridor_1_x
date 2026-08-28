"""Shared read helpers.

Anything that queries "which users are verified" or "what products should
the catalog show" should live here so the same rules are enforced across
public routes, admin, and future contact-reveal.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Sequence
from uuid import UUID

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business_profile import BusinessProfile
from app.models.product import Product
from app.models.profile import Profile
from app.models.user import User, UserStatus


def visible_users_clause():
    """WHERE clause: user is verified and not soft-deleted. Reusable
    wherever we filter by 'can be shown publicly'."""
    return and_(User.status == UserStatus.verified, User.deleted_at.is_(None))


async def verified_seller_ids(db: AsyncSession) -> set[UUID]:
    """User IDs of every verified user who has at least one product.

    One SELECT with a DISTINCT — cheap, and the caller can use the resulting
    set for O(1) 'is this user a seller?' checks over already-loaded rows.
    """
    stmt = (
        select(Product.user_id)
        .join(User, User.id == Product.user_id)
        .where(visible_users_clause())
        .distinct()
    )
    return {row for row in await db.scalars(stmt)}


def public_products_stmt(
    *,
    category: str | None = None,
    variety: str | None = None,
    origin_state: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    min_moq: Decimal | None = None,
    q: str | None = None,
) -> Select[tuple[Product]]:
    """Build a SELECT for products visible in the public catalog.

    Callers add `.offset()` / `.limit()` / `.order_by()` themselves.
    All filters are optional. Everything joins User for the visibility gate.
    """
    stmt = (
        select(Product)
        .join(User, User.id == Product.user_id)
        .where(visible_users_clause())
    )
    if category:
        stmt = stmt.where(Product.category == category)
    if variety:
        stmt = stmt.where(Product.variety.ilike(f"%{variety}%"))
    if origin_state:
        stmt = stmt.where(Product.origin_state == origin_state)
    if min_price is not None:
        stmt = stmt.where(Product.price_per_unit >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price_per_unit <= max_price)
    if min_moq is not None:
        stmt = stmt.where(Product.moq <= min_moq)
    if q:
        # Cheap free-text against name + description. Move to a tsvector
        # (Postgres) or FTS5 (SQLite) index if this grows past 10k products.
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(Product.name.ilike(pattern), Product.description.ilike(pattern))
        )
    return stmt


async def hydrate_sellers(
    db: AsyncSession, seller_ids: Sequence[UUID]
) -> dict[UUID, tuple[Profile | None, BusinessProfile | None]]:
    """Bulk-load Profile + BusinessProfile for a list of user IDs — used
    by the catalog list to avoid N+1 lookups per product card."""
    if not seller_ids:
        return {}
    profiles = {
        p.user_id: p
        for p in await db.scalars(
            select(Profile).where(Profile.user_id.in_(seller_ids))
        )
    }
    businesses = {
        b.user_id: b
        for b in await db.scalars(
            select(BusinessProfile).where(BusinessProfile.user_id.in_(seller_ids))
        )
    }
    return {uid: (profiles.get(uid), businesses.get(uid)) for uid in seller_ids}
