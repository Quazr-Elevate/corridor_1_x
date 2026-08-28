import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models.product import Product
from app.models.user import User
from app.schemas.product import PhotoUploaded, ProductCreate, ProductRead

router = APIRouter(prefix="/products", tags=["products"])

UPLOAD_ROOT = Path("uploads/products")
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
EXT_BY_MIME = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_PHOTOS_PER_PRODUCT = 5


@router.post(
    "/upload-photo",
    response_model=PhotoUploaded,
    response_model_by_alias=True,
    status_code=201,
)
async def upload_photo(
    file: UploadFile = File(...),
    _user: User = Depends(get_current_user),
) -> PhotoUploaded:
    """Accepts a single image file (jpg/png/webp, ≤5 MB) and stores it on disk.
    Returns a relative URL like ``/uploads/products/<uuid>.jpg`` — the frontend
    prepends the API base URL when rendering. In production this handler is
    swapped for an S3/R2 pre-signed upload; the response shape stays the same.
    """
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=400, detail="Only JPG, PNG or WEBP images are supported"
        )
    contents = await file.read()
    if len(contents) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="Image must be under 5 MB")

    filename = f"{uuid.uuid4().hex}{EXT_BY_MIME[file.content_type]}"
    (UPLOAD_ROOT / filename).write_bytes(contents)
    return PhotoUploaded(url=f"/uploads/products/{filename}")


@router.get("", response_model=list[ProductRead], response_model_by_alias=True)
async def list_products(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProductRead]:
    rows = (await db.scalars(select(Product).where(Product.user_id == user.id))).all()
    return [
        ProductRead(
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
            description=p.description,
            photos=p.photos or [],
        )
        for p in rows
    ]


@router.post("", response_model=ProductRead, response_model_by_alias=True, status_code=201)
async def create_product(
    payload: ProductCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProductRead:
    if not payload.photos:
        raise HTTPException(
            status_code=400, detail="At least one product photo is required"
        )
    if len(payload.photos) > MAX_PHOTOS_PER_PRODUCT:
        raise HTTPException(
            status_code=400,
            detail=f"At most {MAX_PHOTOS_PER_PRODUCT} photos per product",
        )

    product = Product(
        user_id=user.id,
        name=payload.name,
        category=payload.category,
        variety=payload.variety,
        origin_state=payload.origin_state,
        packaging=payload.packaging,
        quantity=payload.quantity,
        unit=payload.unit,
        moq=payload.moq,
        price_per_unit=payload.price_per_unit,
        description=payload.description,
        photos=payload.photos,
    )
    db.add(product)
    # Role (seller vs buyer) is derived from the presence of products — no
    # column to flip. This first product is what makes the user a seller.
    await db.commit()
    await db.refresh(product)

    return ProductRead(
        id=str(product.id),
        name=product.name,
        category=product.category,
        variety=product.variety,
        origin_state=product.origin_state,
        packaging=product.packaging,
        quantity=product.quantity,
        unit=product.unit,
        moq=product.moq,
        price_per_unit=product.price_per_unit,
        description=product.description,
        photos=product.photos or [],
    )
