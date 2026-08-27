from app.schemas.base import CamelModel


class PrimaryDetails(CamelModel):
    """Contact + address + additional details + business email (buyers table)."""

    full_name: str
    email: str | None = None
    address_line: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    # Additional
    alt_mobile: str | None = None
    alt_email: str | None = None
    business_email: str | None = None
    website_url: str | None = None
    google_business_url: str | None = None
    facebook_url: str | None = None


class BusinessDetails(CamelModel):
    """GSTIN, PAN, company name (sellers table)."""

    gstin: str | None = None
    pan: str
    company_name: str


class BankDetailsIn(CamelModel):
    account_number: str
    ifsc: str
    holder_name: str
    branch_name: str | None = None
    bank_name: str | None = None


class SellerDetails(CamelModel):
    udyam: str | None = None
    aadhaar: str | None = None
    tan: str | None = None


class ProfileSectionSaved(CamelModel):
    ok: bool = True
