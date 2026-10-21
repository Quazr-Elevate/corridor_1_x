"""Catalog HTTP routes.

* ``products_router`` — /products (business listings, photo upload, soft delete, contact reveal)
* ``public_router``   — /public (anonymous catalog)
* ``uploads_router``  — GET /uploads/products/<file> (public product photos)
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, File, Query, Response, UploadFile

from app.core.security import parse_uuid
from app.modules.auth.deps import CurrentUser, DbSession
from app.modules.catalog import service
from app.modules.catalog.schemas import (
    CatalogFacets,
    PhotoUploaded,
    ProductCreate,
    ProductRead,
    PublicProductDetail,
    PublicProductList,
    RevealedContact,
    product_to_read,
)
from app.shared.files import file_response

products_router = APIRouter(prefix="/products", tags=["products"])
public_router = APIRouter(prefix="/public", tags=["public"])
uploads_router = APIRouter(tags=["uploads"])


# ── /products ────────────────────────────────────────────────────────


@products_router.post("/upload-photo", response_model=PhotoUploaded, response_model_by_alias=True, status_code=201)
async def upload_photo(_user: CurrentUser, file: UploadFile = File(...)) -> PhotoUploaded:
    """JPG/PNG/WEBP (sniffed from content), ≤ 5 MB. Returns
    ``/uploads/products/<hex>.<ext>`` for use in ``POST /products``."""
    content = await file.read(service.MAX_PHOTO_BYTES + 1)
    return PhotoUploaded(url=await service.store_photo(content))


@products_router.get("", response_model=list[ProductRead], response_model_by_alias=True)
async def list_products(user: CurrentUser, db: DbSession) -> list[ProductRead]:
    return [product_to_read(p) for p in await service.list_own_products(db, user)]


@products_router.post("", response_model=ProductRead, response_model_by_alias=True, status_code=201)
async def create_product(payload: ProductCreate, user: CurrentUser, db: DbSession) -> ProductRead:
    return product_to_read(await service.create_product(db, user, payload))


@products_router.delete("/{product_id}", status_code=204, response_class=Response)
async def delete_product(product_id: str, user: CurrentUser, db: DbSession) -> Response:
    await service.delete_product(db, user, parse_uuid(product_id))
    return Response(status_code=204)


@products_router.post("/{product_id}/contact-reveal", response_model=RevealedContact, response_model_by_alias=True)
async def reveal_contact(product_id: str, user: CurrentUser, db: DbSession) -> RevealedContact:
    return await service.reveal_contact(db, user, parse_uuid(product_id))


# ── /public ──────────────────────────────────────────────────────────


@public_router.get("/products", response_model=PublicProductList, response_model_by_alias=True)
async def public_products(
    db: DbSession,
    category: str | None = Query(None, max_length=50),
    variety: str | None = Query(None, max_length=100),
    origin_state: str | None = Query(None, alias="originState", max_length=100),
    min_price: Decimal | None = Query(None, alias="minPrice", ge=0),
    max_price: Decimal | None = Query(None, alias="maxPrice", ge=0),
    price_currency: str | None = Query(
        None, alias="priceCurrency", max_length=3, description="Currency of minPrice/maxPrice (default USD)"
    ),
    min_moq: Decimal | None = Query(None, alias="minMoq", ge=0),
    q: str | None = Query(None, max_length=200),
    limit: int = Query(24, ge=1, le=60),
    offset: int = Query(0, ge=0),
) -> PublicProductList:
    return await service.public_list(
        db,
        category=category,
        variety=variety,
        origin_state=origin_state,
        min_price=min_price,
        max_price=max_price,
        price_currency=price_currency,
        min_moq=min_moq,
        q=q,
        limit=limit,
        offset=offset,
    )


@public_router.get("/products/{product_id}", response_model=PublicProductDetail, response_model_by_alias=True)
async def public_product(product_id: str, db: DbSession) -> PublicProductDetail:
    return await service.public_detail(db, parse_uuid(product_id))


@public_router.get("/catalog/facets", response_model=CatalogFacets, response_model_by_alias=True)
async def catalog_facets(db: DbSession) -> CatalogFacets:
    return await service.facets(db)


# ── /uploads/products/<file> ─────────────────────────────────────────


@uploads_router.get("/uploads/products/{filename}")
async def product_photo(filename: str) -> Response:
    data = await service.read_photo(filename)
    return file_response(data, cache_control="public, max-age=86400, immutable")
