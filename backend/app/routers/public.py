"""Public catalog — anonymous-safe reads.

Contract: nothing here requires auth, and no response ever exposes contact
info (phone / email / address / bank / regulatory IDs). That gate lives on
the Sprint 3 /contact-reveal endpoint, which requires a verified session.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.business_profile import BusinessProfile
from app.models.product import Product
from app.models.profile import Profile
from app.models.user import User
from app.queries import (
    hydrate_sellers,
    public_products_stmt,
    visible_users_clause,
)
from app.schemas.public import (
    CatalogFacets,
    PublicProductCard,
    PublicProductDetail,
    PublicProductList,
    PublicSeller,
)

router = APIRouter(prefix="/public", tags=["public"])


def _seller_dto(
    profile: Profile | None, business: BusinessProfile | None, user_id
) -> PublicSeller:
    return PublicSeller(
        seller_id=str(user_id),
        company_name=(business.company_name if business else None) or "Verified seller",
        city=profile.city if profile else None,
        state=profile.state if profile else None,
    )


def _card_dto(
    p: Product, profile: Profile | None, business: BusinessProfile | None
) -> PublicProductCard:
    return PublicProductCard(
        id=str(p.id),
        name=p.name,
        category=p.category,
        variety=p.variety,
        origin_state=p.origin_state,
        packaging=p.packaging,
        quantity=p.quantity,
        unit=p.unit,
        moq=p.moq,
        price_per_unit=p.price_per_unit,
        photo=(p.photos or [None])[0],
        seller=_seller_dto(profile, business, p.user_id),
    )


@router.get(
    "/products",
    response_model=PublicProductList,
    response_model_by_alias=True,
)
async def list_products(
    category: str | None = Query(None),
    variety: str | None = Query(None),
    origin_state: str | None = Query(None, alias="originState"),
    min_price: Decimal | None = Query(None, alias="minPrice", ge=0),
    max_price: Decimal | None = Query(None, alias="maxPrice", ge=0),
    min_moq: Decimal | None = Query(None, alias="minMoq", ge=0),
    q: str | None = Query(None),
    limit: int = Query(24, ge=1, le=60),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> PublicProductList:
    base = public_products_stmt(
        category=category,
        variety=variety,
        origin_state=origin_state,
        min_price=min_price,
        max_price=max_price,
        min_moq=min_moq,
        q=q,
    )
    total = await db.scalar(
        select(func.count()).select_from(base.subquery())
    ) or 0
    rows = list(
        await db.scalars(
            base.order_by(Product.created_at.desc()).offset(offset).limit(limit)
        )
    )
    seller_map = await hydrate_sellers(db, [r.user_id for r in rows])
    items = [
        _card_dto(r, *seller_map.get(r.user_id, (None, None))) for r in rows
    ]
    return PublicProductList(total=total, items=items)


@router.get(
    "/products/{product_id}",
    response_model=PublicProductDetail,
    response_model_by_alias=True,
)
async def get_product(
    product_id: str,
    db: AsyncSession = Depends(get_db),
) -> PublicProductDetail:
    try:
        pid = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Product not found") from None
    stmt = (
        select(Product)
        .join(User, User.id == Product.user_id)
        .where(Product.id == pid, visible_users_clause())
    )
    p = await db.scalar(stmt)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    seller_map = await hydrate_sellers(db, [p.user_id])
    profile, business = seller_map.get(p.user_id, (None, None))
    card = _card_dto(p, profile, business)
    return PublicProductDetail(
        **card.model_dump(by_alias=False),
        description=p.description,
        photos=p.photos or [],
    )


@router.get(
    "/catalog/facets",
    response_model=CatalogFacets,
    response_model_by_alias=True,
)
async def catalog_facets(db: AsyncSession = Depends(get_db)) -> CatalogFacets:
    """Small aggregate for driving the filter bar. One roundtrip on page
    load; no need to re-fetch per filter change."""
    base = public_products_stmt()

    cats = list(
        await db.execute(
            select(Product.category, func.count(Product.id))
            .join(User, User.id == Product.user_id)
            .where(visible_users_clause())
            .group_by(Product.category)
            .order_by(func.count(Product.id).desc())
        )
    )
    states = list(
        await db.execute(
            select(Product.origin_state, func.count(Product.id))
            .join(User, User.id == Product.user_id)
            .where(visible_users_clause(), Product.origin_state.is_not(None))
            .group_by(Product.origin_state)
            .order_by(func.count(Product.id).desc())
        )
    )
    price_min = await db.scalar(
        select(func.min(Product.price_per_unit)).select_from(base.subquery())
    )
    price_max = await db.scalar(
        select(func.max(Product.price_per_unit)).select_from(base.subquery())
    )
    return CatalogFacets(
        categories=[{"value": c, "count": n} for c, n in cats],
        origin_states=[{"value": s, "count": n} for s, n in states],
        price_min=price_min,
        price_max=price_max,
    )
