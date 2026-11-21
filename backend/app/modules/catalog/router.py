"""Catalog HTTP routes.

* ``products_router`` — /products: a business's own listings (draft, submit,
  edit, pause, delete), photo and certificate uploads, contact reveal
* ``public_router``   — /public: the market, readable without signing in
* ``uploads_router``  — GET /uploads/products/<file> (public product photos)
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, File, Form, Query, Response, UploadFile

from app.core.security import parse_uuid
from app.modules.auth.deps import CurrentUser, DbSession, OptionalUser
from app.modules.catalog import certificates, service
from app.modules.catalog.schemas import (
    CatalogFacets,
    Category,
    CategoryTemplate,
    CertificateOut,
    PhotoUploaded,
    ProductCreate,
    ProductList,
    ProductRead,
    ProductUpdate,
    PublicProductDetail,
    PublicProductList,
    RevealedContact,
)
from app.shared.files import file_response

products_router = APIRouter(prefix="/products", tags=["products"])
public_router = APIRouter(prefix="/public", tags=["public"])
uploads_router = APIRouter(tags=["uploads"])


# ── /products ────────────────────────────────────────────────────────


@products_router.post("/upload-photo", response_model=PhotoUploaded, response_model_by_alias=True, status_code=201)
async def upload_photo(_user: CurrentUser, file: UploadFile = File(...)) -> PhotoUploaded:
    """JPG/PNG/WEBP (sniffed from content), ≤ 5 MB. Returns
    ``/uploads/products/<hex>.<ext>`` for use in a listing's ``photos``."""
    content = await file.read(service.MAX_PHOTO_BYTES + 1)
    return PhotoUploaded(url=await service.store_photo(content))


@products_router.get("", response_model=ProductList, response_model_by_alias=True)
async def list_products(user: CurrentUser, db: DbSession) -> ProductList:
    items = await service.read_products(db, await service.list_own_products(db, user))
    return ProductList(total=len(items), items=items)


@products_router.post("", response_model=ProductRead, response_model_by_alias=True, status_code=201)
async def create_product(payload: ProductCreate, user: CurrentUser, db: DbSession) -> ProductRead:
    """Start a listing as a draft. Only a name and a category are needed."""
    return await service.read_product(db, await service.create_product(db, user, payload))


@products_router.get("/{product_id}", response_model=ProductRead, response_model_by_alias=True)
async def get_product(product_id: str, user: CurrentUser, db: DbSession) -> ProductRead:
    return await service.read_product(db, await service.get_own_product(db, user, parse_uuid(product_id)))


@products_router.patch("/{product_id}", response_model=ProductRead, response_model_by_alias=True)
async def update_product(product_id: str, payload: ProductUpdate, user: CurrentUser, db: DbSession) -> ProductRead:
    """Edit a listing. On a published listing, price and stock change at once;
    other changes wait for a reviewer (see ``pendingRevision``)."""
    return await service.read_product(db, await service.update_product(db, user, parse_uuid(product_id), payload))


@products_router.post("/{product_id}/submit", response_model=ProductRead, response_model_by_alias=True)
async def submit_product(product_id: str, user: CurrentUser, db: DbSession) -> ProductRead:
    return await service.read_product(db, await service.submit_product(db, user, parse_uuid(product_id)))


@products_router.post("/{product_id}/withdraw", response_model=ProductRead, response_model_by_alias=True)
async def withdraw_product(product_id: str, user: CurrentUser, db: DbSession) -> ProductRead:
    return await service.read_product(db, await service.withdraw_product(db, user, parse_uuid(product_id)))


@products_router.post("/{product_id}/pause", response_model=ProductRead, response_model_by_alias=True)
async def pause_product(product_id: str, user: CurrentUser, db: DbSession) -> ProductRead:
    return await service.read_product(db, await service.pause_product(db, user, parse_uuid(product_id)))


@products_router.post("/{product_id}/resume", response_model=ProductRead, response_model_by_alias=True)
async def resume_product(product_id: str, user: CurrentUser, db: DbSession) -> ProductRead:
    return await service.read_product(db, await service.resume_product(db, user, parse_uuid(product_id)))


@products_router.delete("/{product_id}/revision", response_model=ProductRead, response_model_by_alias=True)
async def discard_revision(product_id: str, user: CurrentUser, db: DbSession) -> ProductRead:
    """Drop the edits waiting for review on a published listing."""
    return await service.read_product(db, await service.discard_revision(db, user, parse_uuid(product_id)))


@products_router.delete("/{product_id}", status_code=204, response_class=Response)
async def delete_product(product_id: str, user: CurrentUser, db: DbSession) -> Response:
    await service.delete_product(db, user, parse_uuid(product_id))
    return Response(status_code=204)


@products_router.post(
    "/{product_id}/certificates", response_model=CertificateOut, response_model_by_alias=True, status_code=201
)
async def add_certificate(
    product_id: str,
    user: CurrentUser,
    db: DbSession,
    certificate_type_id: str = Form(..., alias="certificateTypeId", max_length=36),
    file: UploadFile = File(...),
) -> CertificateOut:
    """PDF/JPG/PNG/WEBP (sniffed), ≤ 10 MB; one file per certificate type.
    Internal until an admin marks it downloadable."""
    content = await file.read(certificates.MAX_CERTIFICATE_BYTES + 1)
    return await certificates.add_certificate(
        db, user, parse_uuid(product_id), parse_uuid(certificate_type_id), file.filename, content
    )


@products_router.delete("/{product_id}/certificates/{certificate_id}", status_code=204, response_class=Response)
async def delete_certificate(product_id: str, certificate_id: str, user: CurrentUser, db: DbSession) -> Response:
    await certificates.delete_certificate(db, user, parse_uuid(product_id), parse_uuid(certificate_id))
    return Response(status_code=204)


@products_router.get("/{product_id}/certificates/{certificate_id}/file")
async def certificate_file(product_id: str, certificate_id: str, user: CurrentUser, db: DbSession) -> Response:
    """The listing's own business always; a verified buyer when an admin
    approved the download (each one is logged)."""
    filename, data = await certificates.open_certificate(db, user, parse_uuid(product_id), parse_uuid(certificate_id))
    return file_response(data, filename=filename, cache_control="private, no-store")


@products_router.post("/{product_id}/contact-reveal", response_model=RevealedContact, response_model_by_alias=True)
async def reveal_contact(product_id: str, user: CurrentUser, db: DbSession) -> RevealedContact:
    return await service.reveal_contact(db, user, parse_uuid(product_id))


# ── /public ──────────────────────────────────────────────────────────


@public_router.get("/products", response_model=PublicProductList, response_model_by_alias=True)
async def public_products(
    db: DbSession,
    viewer: OptionalUser,
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
    """The market. Open to everyone; the price range and price filters are
    only for a signed-in, verified business."""
    return await service.public_list(
        db,
        viewer=viewer,
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
async def public_product(product_id: str, db: DbSession, viewer: OptionalUser) -> PublicProductDetail:
    return await service.public_detail(db, parse_uuid(product_id), viewer)


@public_router.get("/catalog/facets", response_model=CatalogFacets, response_model_by_alias=True)
async def catalog_facets(db: DbSession, viewer: OptionalUser) -> CatalogFacets:
    return await service.facets(db, viewer)


@public_router.get("/catalog/template", response_model=CategoryTemplate, response_model_by_alias=True)
async def catalog_template(db: DbSession, category: Category = Query(...)) -> CategoryTemplate:
    """What a listing in this category is asked for: specification rows and
    documents. Reference data, deliberately public."""
    return await service.category_template(db, category)


# ── /uploads/products/<file> ─────────────────────────────────────────


@uploads_router.get("/uploads/products/{filename}")
async def product_photo(filename: str) -> Response:
    data = await service.read_photo(filename)
    return file_response(data, cache_control="public, max-age=86400, immutable")
