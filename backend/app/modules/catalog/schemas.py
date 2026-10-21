"""Catalog schemas — seller products, the public catalog, contact reveal.

Public shapes are STRICT: no contact info (email, address, bank, IDs).
That only leaves the backend through the contact-reveal endpoint.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.models.product import Product
from pydantic import StringConstraints

from app.shared.schemas import CamelModel, text

Category = Literal[
    "Rice", "Sugar", "Wheat", "Pulses", "Spices", "Oilseeds",
    "Cotton", "Millets", "Tea", "Coffee", "Other",
]
Unit = Literal["MT", "kg", "quintal"]
Packaging = Literal["Jute", "PP woven", "HDPE", "Bulk", "Other"]

# Numeric(12, 2) columns.
Amount = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]

MAX_PHOTOS_PER_PRODUCT = 5
MAX_DESCRIPTION = 5000

Currency = Annotated[str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Z]{3}$")]

ProductName = text(200, 2)
ShortField = text(100)
Description = text(MAX_DESCRIPTION)


# ── Seller products ──────────────────────────────────────────────────


class ProductCreate(CamelModel):
    name: ProductName  # type: ignore[valid-type]
    category: Category
    variety: ShortField | None = None  # type: ignore[valid-type]
    origin_state: ShortField | None = None  # type: ignore[valid-type]
    packaging: Packaging | None = None
    quantity: Amount | None = None
    unit: Unit = "MT"
    moq: Amount | None = None
    price_per_unit: Amount | None = None
    description: Description | None = None  # type: ignore[valid-type]
    currency: Currency = "INR"
    # URLs returned by POST /products/upload-photo. 1..5 required —
    # checked in the service for friendlier messages.
    photos: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _moq_within_quantity(self) -> "ProductCreate":
        if self.moq is not None and self.quantity is not None and self.moq > self.quantity:
            raise ValueError("MOQ can't be larger than the available quantity.")
        return self


class ProductRead(CamelModel):
    id: str
    name: str
    category: str
    variety: str | None = None
    origin_state: str | None = None
    packaging: str | None = None
    quantity: Decimal | None = None
    unit: str
    moq: Decimal | None = None
    price_per_unit: Decimal | None = None
    currency: str = "INR"
    price_usd: Decimal | None = None
    price_usd_as_of: date | None = None
    description: str | None = None
    photos: list[str] = []


def product_to_read(p: Product) -> ProductRead:
    return ProductRead(
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
        description=p.description,
        photos=list(p.photos or []),
    )


class PhotoUploaded(CamelModel):
    url: str


# ── Public catalog ───────────────────────────────────────────────────


class PublicSeller(CamelModel):
    """Business name + city + verified badge only. ``seller_id`` is the
    seller BUSINESS id."""

    seller_id: str
    business_name: str
    city: str | None = None
    state: str | None = None
    verified: bool = True  # Reserved for when we differentiate tiers.


class PublicProductCard(CamelModel):
    id: str
    name: str
    category: str
    variety: str | None = None
    origin_state: str | None = None
    packaging: str | None = None
    quantity: Decimal | None = None
    unit: str
    moq: Decimal | None = None
    price_per_unit: Decimal | None = None
    currency: str = "INR"
    # Indicative USD value (latest rate on price_usd_as_of) — for comparing
    # across currencies; the seller's price above is the real one.
    price_usd: Decimal | None = None
    price_usd_as_of: date | None = None
    photo: str | None = None  # first photo only — detail has the gallery
    seller: PublicSeller


class PublicProductDetail(PublicProductCard):
    description: str | None = None
    photos: list[str] = []


class PublicProductList(CamelModel):
    total: int
    items: list[PublicProductCard]


class CatalogFacets(CamelModel):
    categories: list[dict[str, int | str]]
    origin_states: list[dict[str, int | str]]
    # Range of price_usd over visible listings (USD).
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    price_currency: str = "USD"
    fx_as_of: date | None = None


# ── Contact reveal ───────────────────────────────────────────────────


class RevealedContact(CamelModel):
    """What a verified buyer business sees after unlocking a seller's
    contact: the seller owner's name + work email, business name, entity
    type and address. ``seller_id`` is the seller business id."""

    seller_id: str
    full_name: str | None
    business_name: str | None
    entity_type: str | None
    email: str | None
    address_line: str | None
    city: str | None
    state: str | None
    pincode: str | None
    country: str | None
    website_url: str | None
    revealed_at: datetime
