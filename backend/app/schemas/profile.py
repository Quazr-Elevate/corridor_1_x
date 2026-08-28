from app.schemas.base import CamelModel


class PrimaryDetails(CamelModel):
    """Personal profile — name, email, address, alt contacts, socials.
    Written to the `profiles` table. Applies to every user (buyer or seller)."""

    full_name: str
    email: str | None = None
    address_line: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    country: str | None = None
    # Additional
    alt_mobile: str | None = None
    alt_email: str | None = None
    business_email: str | None = None
    website_url: str | None = None
    google_business_url: str | None = None
    facebook_url: str | None = None


class BusinessDetails(CamelModel):
    """Business identity — GSTIN, PAN, company name. Written to
    `business_profiles`. Optional for buyers, required for verified sellers."""

    gstin: str | None = None
    pan: str
    company_name: str
    business_type: str | None = None
    nature_of_business: str | None = None


class BankDetailsIn(CamelModel):
    """Bank/payout account. Written into the `bank_*` columns on the same
    `business_profiles` row as BusinessDetails (was a separate table pre-0006)."""

    account_number: str
    ifsc: str
    holder_name: str
    branch_name: str | None = None
    bank_name: str | None = None


class RegulatoryDetails(CamelModel):
    """Extra IDs a seller may add — Udyam / Aadhaar / TAN.
    Written to `business_profiles`."""

    udyam: str | None = None
    aadhaar: str | None = None
    tan: str | None = None


class ProfileSectionSaved(CamelModel):
    ok: bool = True
