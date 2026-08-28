from __future__ import annotations

from datetime import datetime

from app.schemas.base import CamelModel


class RevealedContact(CamelModel):
    """What a verified buyer sees when they unlock a seller's contact.

    Deliberately narrow — mobile + primary email + business email + full
    address + company name. No Aadhaar, no PAN, no GSTIN, no bank. Those
    stay admin-only.
    """

    seller_id: str
    full_name: str | None
    company_name: str | None
    business_type: str | None
    mobile: str | None
    email: str | None
    business_email: str | None
    address_line: str | None
    city: str | None
    state: str | None
    pincode: str | None
    country: str | None
    website_url: str | None
    revealed_at: datetime


class AdminRecentReveal(CamelModel):
    """One row on the admin recent-reveals feed."""

    reveal_id: str
    buyer_id: str
    buyer_name: str | None
    seller_id: str
    seller_company: str | None
    product_id: str
    product_name: str
    revealed_at: datetime
