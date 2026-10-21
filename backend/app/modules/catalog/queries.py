"""Shared read helpers: "which products the market shows" — one
definition for public routes, reveals and admin."""
from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business, BusinessStatus
from app.models.product import Product


def visible_products_clause():
    """Product not deleted AND owning business verified and not deleted
    (the caller joins ``Business`` on ``Product.business_id``)."""
    return and_(
        Product.deleted_at.is_(None),
        Business.verification_status == BusinessStatus.verified,
        Business.deleted_at.is_(None),
    )


def visible_products_select() -> Select[tuple[Product]]:
    return select(Product).join(Business, Business.id == Product.business_id).where(visible_products_clause())


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def public_products_stmt(
    *,
    category: str | None = None,
    variety: str | None = None,
    origin_state: str | None = None,
    min_price_usd: Decimal | None = None,
    max_price_usd: Decimal | None = None,
    min_moq: Decimal | None = None,
    q: str | None = None,
) -> Select[tuple[Product]]:
    """SELECT of market-visible products; callers add order/offset/limit.
    Price bounds are in USD and compare ``price_usd`` (any listing currency)."""
    stmt = visible_products_select()
    if category:
        stmt = stmt.where(Product.category == category)
    if variety:
        stmt = stmt.where(Product.variety.ilike(f"%{_escape_like(variety.strip())}%", escape="\\"))
    if origin_state:
        stmt = stmt.where(Product.origin_state == origin_state)
    if min_price_usd is not None:
        stmt = stmt.where(Product.price_usd >= min_price_usd)
    if max_price_usd is not None:
        stmt = stmt.where(Product.price_usd <= max_price_usd)
    if min_moq is not None:
        stmt = stmt.where(Product.moq <= min_moq)
    if q and q.strip():
        # Cheap free-text; move to tsvector / FTS5 past ~10k products.
        pattern = f"%{_escape_like(q.strip())}%"
        stmt = stmt.where(
            or_(Product.name.ilike(pattern, escape="\\"), Product.description.ilike(pattern, escape="\\"))
        )
    return stmt


async def hydrate_businesses(db: AsyncSession, business_ids: Sequence[UUID]) -> dict[UUID, Business]:
    """Bulk-load the seller businesses of many products (no N+1)."""
    ids = list(set(business_ids))
    if not ids:
        return {}
    return {b.id: b for b in await db.scalars(select(Business).where(Business.id.in_(ids)))}
