from app.schemas.base import CamelModel


class Completion(CamelModel):
    """Which profile sections are filled — drives sidebar ticks + product gate.

    The `seller` flag is a legacy name for "regulatory extras present"
    (udyam / aadhaar / tan). Kept as-is for frontend compatibility."""

    primary: bool
    business: bool
    bank: bool
    seller: bool


class PrimaryData(CamelModel):
    full_name: str | None = None
    email: str | None = None
    address_line: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    country: str | None = None
    alt_mobile: str | None = None
    alt_email: str | None = None
    business_email: str | None = None
    website_url: str | None = None
    google_business_url: str | None = None
    facebook_url: str | None = None


class BusinessData(CamelModel):
    gstin: str | None = None
    pan: str | None = None
    company_name: str | None = None
    business_type: str | None = None
    nature_of_business: str | None = None


class BankData(CamelModel):
    account_number: str | None = None
    ifsc: str | None = None
    holder_name: str | None = None
    branch_name: str | None = None
    bank_name: str | None = None


class RegulatoryData(CamelModel):
    udyam: str | None = None
    aadhaar: str | None = None
    tan: str | None = None


class MeResponse(CamelModel):
    user_id: str
    # Derived from products count. 'buyer' by default; 'seller' if the user
    # has at least one product.
    user_type: str
    status: str
    mobile: str
    full_name: str | None = None
    completion: Completion
    primary: PrimaryData
    business: BusinessData
    bank: BankData
    # Kept as `seller` in the response for frontend-compat with the pulled UI;
    # semantically these are regulatory IDs on the business profile.
    seller: RegulatoryData


class IfscLookup(CamelModel):
    ifsc: str
    bank: str
    branch: str
    city: str | None = None
    state: str | None = None
