"""Catalog rules: photo uploads, seller listings, public catalog, contact
reveal."""
from __future__ import annotations

import re
import uuid
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequest, Forbidden, NotFound, PayloadTooLarge, TooManyRequests, UnsupportedMediaType
from app.core.time import utcnow
from app.integrations.storage import IMAGE_TYPES, StorageError, detect, get_storage
from app.models.business import Business
from app.models.contact_reveal import ContactReveal
from app.models.product import Product
from app.models.user import User
from app.modules.accounts.service import get_owner
from app.modules.accounts.uniqueness import commit_or_conflict
from app.modules.catalog.queries import hydrate_businesses, public_products_stmt, visible_products_select
from app.modules.fx import service as fx
from app.modules.catalog.schemas import (
    MAX_PHOTOS_PER_PRODUCT,
    CatalogFacets,
    ProductCreate,
    PublicProductCard,
    PublicProductDetail,
    PublicProductList,
    PublicSeller,
    RevealedContact,
)

MAX_PHOTO_BYTES = 5 * 1024 * 1024
PHOTO_PREFIX = "products"
PHOTO_URL_PREFIX = "/uploads/products/"
PHOTO_FILENAME_RE = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp)$")

REVEAL_WINDOW = timedelta(hours=1)
REVEAL_MAX_PER_WINDOW = 20


# ── Photos ───────────────────────────────────────────────────────────


def photo_key(filename: str) -> str | None:
    """Storage key for a served photo filename, or None if malformed."""
    return f"{PHOTO_PREFIX}/{filename}" if PHOTO_FILENAME_RE.match(filename) else None


async def store_photo(content: bytes) -> str:
    """Validate by magic bytes, store, return the public relative URL."""
    if not content:
        raise BadRequest("Empty file.")
    if len(content) > MAX_PHOTO_BYTES:
        raise PayloadTooLarge("Image must be under 5 MB")
    ftype = detect(content)
    if ftype is None or ftype not in IMAGE_TYPES:
        raise UnsupportedMediaType("Only JPG, PNG or WEBP images are supported")
    filename = f"{uuid.uuid4().hex}.{ftype.ext}"
    await get_storage().save(content, f"{PHOTO_PREFIX}/{filename}", ftype.mime)
    return f"{PHOTO_URL_PREFIX}{filename}"


async def read_photo(filename: str) -> bytes:
    key = photo_key(filename)
    if key is None:
        raise NotFound("Not found")
    try:
        return await get_storage().open(key)
    except StorageError:
        raise NotFound("Not found") from None


async def _validate_photos(photos: list[str]) -> list[str]:
    unique = list(dict.fromkeys(p.strip() for p in photos if p and p.strip()))
    if not unique:
        raise BadRequest("At least one product photo is required")
    if len(unique) > MAX_PHOTOS_PER_PRODUCT:
        raise BadRequest(f"At most {MAX_PHOTOS_PER_PRODUCT} photos per product")
    storage = get_storage()
    for url in unique:
        filename = url[len(PHOTO_URL_PREFIX):] if url.startswith(PHOTO_URL_PREFIX) else ""
        key = photo_key(filename)
        if key is None or not await storage.exists(key):
            raise BadRequest("Photos must be uploaded via /products/upload-photo first.")
    return unique


# ── Seller products ──────────────────────────────────────────────────


async def list_own_products(db: AsyncSession, user: User) -> list[Product]:
    """The business's listings (not deleted), newest first."""
    return list(
        await db.scalars(
            select(Product)
            .where(Product.business_id == user.business_id, Product.deleted_at.is_(None))
            .order_by(Product.created_at.desc())
        )
    )


async def create_product(db: AsyncSession, user: User, payload: ProductCreate) -> Product:
    """Any signed-in user may list for their business; listings only appear
    in the market once the business is verified (``visible_products_clause``)."""
    currency = fx.ensure_supported(payload.currency)
    photos = await _validate_photos(payload.photos)
    price_usd, price_usd_as_of = fx.price_usd_for(payload.price_per_unit, currency, await fx.get_latest_rates(db))
    product = Product(
        business_id=user.business_id,
        created_by_user_id=user.id,
        name=payload.name,
        category=payload.category,
        variety=payload.variety or None,
        origin_state=payload.origin_state or None,
        packaging=payload.packaging,
        quantity=payload.quantity,
        unit=payload.unit,
        moq=payload.moq,
        price_per_unit=payload.price_per_unit,
        currency=currency,
        price_usd=price_usd,
        price_usd_as_of=price_usd_as_of,
        description=payload.description or None,
        photos=photos,
    )
    db.add(product)
    await commit_or_conflict(db)
    await db.refresh(product)
    return product


async def delete_product(db: AsyncSession, user: User, product_id: uuid.UUID | None) -> None:
    """Soft delete (the listing leaves the market; reveals keep their history)."""
    product = await db.get(Product, product_id) if product_id else None
    if product is None or product.business_id != user.business_id or product.deleted_at is not None:
        raise NotFound("Product not found")
    product.deleted_at = utcnow()
    await db.commit()


# ── Public catalog ───────────────────────────────────────────────────


def _seller_dto(business: Business | None, business_id: uuid.UUID) -> PublicSeller:
    return PublicSeller(
        seller_id=str(business_id),
        city=business.city if business else None,
        state=business.state if business else None,
    )


def _card_kwargs(p: Product, business: Business | None) -> dict:
    return dict(
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
        currency=p.currency,
        price_usd=p.price_usd,
        price_usd_as_of=p.price_usd_as_of,
        photo=(p.photos or [None])[0],
        seller=_seller_dto(business, p.business_id),
    )


async def public_list(
    db: AsyncSession,
    *,
    category: str | None,
    variety: str | None,
    origin_state: str | None,
    min_price: Decimal | None,
    max_price: Decimal | None,
    min_moq: Decimal | None,
    q: str | None,
    limit: int,
    offset: int,
    price_currency: str | None = None,
) -> PublicProductList:
    """Price bounds are typed in ``price_currency`` (default USD), converted
    to USD with the latest rates and compared with ``price_usd``."""
    min_usd, max_usd = await fx.usd_bounds(db, min_price, max_price, price_currency)
    base = public_products_stmt(
        category=category,
        variety=variety,
        origin_state=origin_state,
        min_price_usd=min_usd,
        max_price_usd=max_usd,
        min_moq=min_moq,
        q=q,
    )
    total = await db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(await db.scalars(base.order_by(Product.created_at.desc()).offset(offset).limit(limit)))
    sellers = await hydrate_businesses(db, [r.business_id for r in rows])
    items = [PublicProductCard(**_card_kwargs(r, sellers.get(r.business_id))) for r in rows]
    return PublicProductList(total=total, items=items)


async def _visible_product(db: AsyncSession, product_id: uuid.UUID | None) -> Product:
    if product_id is None:
        raise NotFound("Product not found")
    product = await db.scalar(visible_products_select().where(Product.id == product_id))
    if product is None:
        raise NotFound("Product not found")
    return product


async def public_detail(db: AsyncSession, product_id: uuid.UUID | None) -> PublicProductDetail:
    p = await _visible_product(db, product_id)
    business = await db.get(Business, p.business_id)
    return PublicProductDetail(
        **_card_kwargs(p, business),
        description=p.description,
        photos=list(p.photos or []),
    )


async def facets(db: AsyncSession) -> CatalogFacets:
    visible = visible_products_select().subquery()
    cats = (
        await db.execute(
            select(visible.c.category, func.count())
            .group_by(visible.c.category)
            .order_by(func.count().desc())
        )
    ).all()
    states = (
        await db.execute(
            select(visible.c.origin_state, func.count())
            .where(visible.c.origin_state.is_not(None))
            .group_by(visible.c.origin_state)
            .order_by(func.count().desc())
        )
    ).all()
    price_min, price_max = (
        await db.execute(select(func.min(visible.c.price_usd), func.max(visible.c.price_usd)))
    ).one()
    rates = await fx.get_latest_rates(db)
    return CatalogFacets(
        categories=[{"value": c, "count": n} for c, n in cats],
        origin_states=[{"value": s, "count": n} for s, n in states],
        price_min=price_min,
        price_max=price_max,
        price_currency=fx.BASE,
        fx_as_of=rates.as_of,
    )


# ── Contact reveal ───────────────────────────────────────────────────


async def _check_reveal_budget(db: AsyncSession, buyer_business_id: uuid.UUID) -> None:
    """DB-backed (survives restarts, shared across workers): at most
    REVEAL_MAX_PER_WINDOW *new* reveals per buyer BUSINESS per hour."""
    since = utcnow() - REVEAL_WINDOW
    recent = await db.scalar(
        select(func.count(ContactReveal.id)).where(
            ContactReveal.buyer_business_id == buyer_business_id, ContactReveal.revealed_at >= since
        )
    ) or 0
    if recent >= REVEAL_MAX_PER_WINDOW:
        raise TooManyRequests(
            f"Your business hit the reveal limit ({REVEAL_MAX_PER_WINDOW}/hour). Come back shortly.",
            retry_after=int(REVEAL_WINDOW.total_seconds()),
        )


async def reveal_contact(db: AsyncSession, user: User, product_id: uuid.UUID | None) -> RevealedContact:
    """Business-to-business. Gates: signed in (router), buyer business
    verified, product visible (seller business verified), not own
    business, per-business hourly budget. Idempotent per (buyer business,
    product)."""
    buyer = user.business
    if not buyer.is_verified:
        raise Forbidden("Get your business verified before revealing seller contact details.")
    product = await _visible_product(db, product_id)
    # Plain values: a rollback below expires ORM instances.
    seller_id, pid, buyer_id, user_id = product.business_id, product.id, buyer.id, user.id
    if seller_id == buyer_id:
        raise BadRequest("This is your own business's listing — nothing to reveal.")

    def _existing_stmt():
        return select(ContactReveal).where(
            ContactReveal.buyer_business_id == buyer_id, ContactReveal.product_id == pid
        )

    existing = await db.scalar(_existing_stmt())
    if existing is None:
        await _check_reveal_budget(db, buyer_id)
        revealed_at = utcnow()
        db.add(
            ContactReveal(
                buyer_business_id=buyer_id,
                revealed_by_user_id=user_id,
                seller_business_id=seller_id,
                product_id=pid,
                revealed_at=revealed_at,
            )
        )
        try:
            await db.commit()
        except IntegrityError:  # double-click race on UNIQUE(buyer business, product)
            await db.rollback()
            existing = await db.scalar(_existing_stmt())
            if existing is None:
                raise
            revealed_at = existing.revealed_at
    else:
        revealed_at = existing.revealed_at

    seller = await db.get(Business, seller_id)
    owner = await get_owner(db, seller_id)
    assert seller is not None  # guarded by visible_products_clause
    return RevealedContact(
        seller_id=str(seller.id),
        full_name=owner.full_name if owner else None,
        business_name=seller.legal_name,
        entity_type=seller.entity_type,
        email=owner.email if owner else None,
        address_line=seller.address_line,
        city=seller.city,
        state=seller.state,
        pincode=seller.pincode,
        country=seller.country,
        website_url=seller.website_url,
        revealed_at=revealed_at,
    )
