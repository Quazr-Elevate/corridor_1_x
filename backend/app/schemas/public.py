"""Public-catalog response shapes.

STRICT: no contact info (mobile, email, alt contacts, full address,
bank, regulatory IDs) leaves this schema. Everything a card or detail
page needs to render — but nothing an anonymous browser could use to
bypass the contact-reveal gate.
"""
from __future__ import annotations

from decimal import Decimal

from app.schemas.base import CamelModel


class PublicSeller(CamelModel):
    """The seller-facing side of a card. Company + city + verified badge
    only — no name, mobile, email, address, or IDs."""

    seller_id: str
    company_name: str
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
    # First photo only — detail returns the full list.
    photo: str | None = None
    seller: PublicSeller


class PublicProductDetail(PublicProductCard):
    """Card + description + full photo gallery."""

    description: str | None = None
    photos: list[str] = []


class PublicProductList(CamelModel):
    total: int
    items: list[PublicProductCard]


class CatalogFacets(CamelModel):
    """Aggregate metadata for building filter chips — categories with counts,
    states, price bounds. Cheaper than the client computing this itself."""

    categories: list[dict[str, int | str]]
    origin_states: list[dict[str, int | str]]
    price_min: Decimal | None = None
    price_max: Decimal | None = None
