from app.schemas.base import CamelModel


class PrimaryDetails(CamelModel):
    """Personal profile — name, address, socials. Applies to every user."""

    full_name: str
    address_line: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    country: str | None = None
    website_url: str | None = None
    google_business_url: str | None = None
    facebook_url: str | None = None


class BusinessDetails(CamelModel):
    """Business identity — free-text metadata only (no regulated IDs).

    Regulated IDs (GST, PAN, Aadhaar) live in a separate KYB flow; the
    marketplace-side account no longer stores them.
    """

    business_type: str | None = None
    nature_of_business: str | None = None
    udyam: str | None = None


class BankDetailsIn(CamelModel):
    """Bank/payout account."""

    account_number: str
    ifsc: str
    holder_name: str
    branch_name: str | None = None
    bank_name: str | None = None


class ProfileSectionSaved(CamelModel):
    ok: bool = True
