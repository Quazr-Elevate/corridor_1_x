"""Catalog schemas — seller listings, category templates, the public
catalog, contact reveal.

Public shapes are STRICT: no contact info (email, address, bank, IDs).
That only leaves the backend through the contact-reveal endpoint.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, ValidationInfo, field_validator

from pydantic import StringConstraints

from app.shared.schemas import CamelModel, CountryCode, RequestModel, text

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

Operator = Literal["MIN", "MAX", "EQ"]
Incoterm = Literal["EXW", "FOB", "CIF", "CFR", "DAP", "DDP"]
HsCode = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[0-9]{6,10}$")]

#: Changes to these go live at once on a published listing (they move daily).
#: Every other field waits for a reviewer (decision A-021).
LIVE_FIELDS = frozenset({"quantity", "moq", "price_min", "price_max", "currency", "price_valid_until"})


class SpecIn(RequestModel):
    """The seller's value for one parameter of the category template."""

    parameter_id: str
    value: text(200, 1)  # type: ignore[valid-type]
    operator: Operator | None = None  # defaults to the parameter's
    test_method: text(100) | None = None  # type: ignore[valid-type]


class ProductUpdate(RequestModel):
    """Any subset of a listing's fields. A draft needs only a name and a
    category; the rest is checked when the listing is submitted."""

    name: ProductName | None = None  # type: ignore[valid-type]
    category: Category | None = None
    variety: ShortField | None = None  # type: ignore[valid-type]
    description: Description | None = None  # type: ignore[valid-type]
    grade: ShortField | None = None  # type: ignore[valid-type]
    hs_code: HsCode | None = None
    origin_country: CountryCode | None = None
    origin_state: ShortField | None = None  # type: ignore[valid-type]
    packaging: Packaging | None = None
    quantity: Amount | None = None
    unit: Unit | None = None
    moq: Amount | None = None
    capacity_per_month: Amount | None = None
    capacity_unit: Unit | None = None
    lead_time_days: int | None = Field(None, ge=0, le=730)
    price_min: Amount | None = None
    price_max: Amount | None = None
    currency: Currency | None = None
    price_valid_until: date | None = None
    incoterms: list[Incoterm] | None = Field(None, max_length=6)
    port_of_loading: ShortField | None = None  # type: ignore[valid-type]
    # URLs returned by POST /products/upload-photo (at most 5).
    photos: list[str] | None = Field(None, max_length=20)
    # Replaces the listing's specification rows.
    specs: list[SpecIn] | None = Field(None, max_length=60)

    # Field validators, not a model validator, so the error names the box to
    # fix (``moq``, ``priceMax``); each reads the field declared before it.
    @field_validator("moq")
    @classmethod
    def _moq_within_quantity(cls, moq: Decimal | None, info: ValidationInfo) -> Decimal | None:
        quantity = info.data.get("quantity")
        if moq is not None and quantity is not None and moq > quantity:
            raise ValueError("MOQ can't be larger than the available quantity.")
        return moq

    @field_validator("price_min", "price_max")
    @classmethod
    def _price_above_zero(cls, price: Decimal | None) -> Decimal | None:
        if price is not None and price <= 0:
            raise ValueError("Price must be greater than 0.")
        return price

    @field_validator("price_max")
    @classmethod
    def _max_not_below_min(cls, price_max: Decimal | None, info: ValidationInfo) -> Decimal | None:
        price_min = info.data.get("price_min")
        if price_max is not None and price_min is not None and price_max < price_min:
            raise ValueError("The maximum price can't be lower than the minimum price.")
        return price_max


class ProductCreate(ProductUpdate):
    name: ProductName  # type: ignore[valid-type]
    category: Category


class SpecOut(CamelModel):
    parameter_id: str
    code: str
    name: str
    unit: str | None = None
    value: str
    operator: str
    test_method: str | None = None


class CertificateOut(CamelModel):
    id: str
    certificate_type_id: str
    code: str
    name: str
    filename: str
    mime_type: str
    size_bytes: int
    # internal | downloadable — set by an admin; buyers only get "downloadable".
    visibility: str
    uploaded_at: datetime
    url: str


class ProductRead(CamelModel):
    id: str
    name: str
    category: str
    variety: str | None = None
    description: str | None = None
    grade: str | None = None
    hs_code: str | None = None
    origin_country: str | None = None
    origin_state: str | None = None
    packaging: str | None = None
    quantity: Decimal | None = None
    unit: str
    moq: Decimal | None = None
    capacity_per_month: Decimal | None = None
    capacity_unit: str | None = None
    lead_time_days: int | None = None
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    currency: str = "INR"
    price_usd: Decimal | None = None
    price_usd_max: Decimal | None = None
    price_usd_as_of: date | None = None
    price_valid_until: date | None = None
    incoterms: list[str] = []
    port_of_loading: str | None = None
    photos: list[str] = []
    specs: list[SpecOut] = []
    certificates: list[CertificateOut] = []
    # draft | under_review | published | rejected | paused
    status: str
    submitted_at: datetime | None = None
    published_at: datetime | None = None
    rejection_reason: str | None = None
    # Edits to a published listing that a reviewer has not approved yet
    # (camelCase field → proposed value); the published values stay live.
    pending_revision: dict | None = None
    #: True when this save (or an earlier one) is waiting for a reviewer: the
    #: listing shown is still the approved version (see ``pendingRevision``).
    has_pending_revision: bool = False
    revision_submitted_at: datetime | None = None
    revision_rejection_reason: str | None = None
    # What is still needed before this listing can be submitted.
    missing: list[str] = []
    created_at: datetime
    updated_at: datetime


class ProductList(CamelModel):
    total: int
    items: list[ProductRead]


class PhotoUploaded(CamelModel):
    url: str


# ── Category template ────────────────────────────────────────────────


class SpecParameterOut(CamelModel):
    id: str
    category: str
    code: str
    name: str
    value_type: str
    unit: str | None = None
    default_operator: str
    test_method: str | None = None
    is_required: bool
    sort_order: int
    active: bool


class CertificateTypeOut(CamelModel):
    id: str
    # A product category, or "*" for every category.
    category: str
    code: str
    name: str
    help_text: str | None = None
    is_required: bool
    sort_order: int
    active: bool


class CategoryTemplate(CamelModel):
    """What a listing in this category is asked for."""

    category: str
    spec_parameters: list[SpecParameterOut]
    certificate_types: list[CertificateTypeOut]


# ── Public catalog ───────────────────────────────────────────────────


class PublicSeller(CamelModel):
    """The seller as another party sees it: the company code, the state and
    the verified badge. Never the name, the city or a contact detail — a
    city plus a commodity is often enough to name the seller — and never the
    internal business id."""

    company_code: str | None = None
    state: str | None = None
    verified: bool = True  # Reserved for when we differentiate tiers.


class PublicProductCard(CamelModel):
    id: str
    name: str
    category: str
    variety: str | None = None
    grade: str | None = None
    origin_country: str | None = None
    origin_state: str | None = None
    packaging: str | None = None
    quantity: Decimal | None = None
    unit: str
    moq: Decimal | None = None
    capacity_per_month: Decimal | None = None
    capacity_unit: str | None = None
    incoterms: list[str] = []
    # The price range is for signed-in, verified businesses (decision A-022).
    # For everyone else price_visible is false and every price field is null.
    price_visible: bool = False
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    currency: str | None = None
    # Indicative USD values (latest rate on price_usd_as_of) — for comparing
    # across currencies; the seller's range above is the real one.
    price_usd: Decimal | None = None
    price_usd_max: Decimal | None = None
    price_usd_as_of: date | None = None
    price_valid_until: date | None = None
    photo: str | None = None  # first photo only — detail has the gallery
    seller: PublicSeller


class PublicCertificate(CamelModel):
    """A certificate an admin approved for download. The filename is not
    shown: it often carries the seller's name."""

    id: str
    name: str
    url: str


class PublicProductDetail(PublicProductCard):
    description: str | None = None
    photos: list[str] = []
    specs: list[SpecOut] = []
    certificates: list[PublicCertificate] = []


class PublicProductList(CamelModel):
    total: int
    items: list[PublicProductCard]


class CatalogFacets(CamelModel):
    categories: list[dict[str, int | str]]
    origin_states: list[dict[str, int | str]]
    # Range of price_usd over visible listings (USD); null unless the viewer
    # may see prices.
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
