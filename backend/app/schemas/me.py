from datetime import datetime

from app.schemas.base import CamelModel


class Completion(CamelModel):
    """Which optional sections are filled — drives sidebar ticks and gates."""

    primary: bool
    business: bool
    bank: bool


class PrimaryData(CamelModel):
    """Personal profile — filled during signup + onboarding step 2."""

    full_name: str | None = None
    phone: str | None = None
    department: str | None = None
    position: str | None = None
    address_line: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    country: str | None = None
    website_url: str | None = None
    google_business_url: str | None = None
    facebook_url: str | None = None


class BusinessData(CamelModel):
    """Business identity — company info + business profile sections."""

    # Company info (onboarding step 1)
    legal_name: str | None = None
    industry: str | None = None
    operating_countries: list[str] | None = None
    website_url: str | None = None
    # Business profile (onboarding step 3)
    trade_position: str | None = None
    seller_type: str | None = None
    business_role: str | None = None
    export_status: str | None = None
    target_markets: list[str] | None = None
    target_buyer_types: list[str] | None = None
    main_objective: str | None = None
    company_introduction: str | None = None
    # Free-text extras
    business_type: str | None = None
    nature_of_business: str | None = None
    udyam: str | None = None


class BankData(CamelModel):
    account_number: str | None = None
    ifsc: str | None = None
    ifsc_verified_at: datetime | None = None
    holder_name: str | None = None
    branch_name: str | None = None
    bank_name: str | None = None


class VerificationState(CamelModel):
    """Current state of the Verified-badge flow.

    ``status`` mirrors ``users.status`` ("active" | "pending_verification"
    | "verified" | "rejected") so the frontend can switch the progress
    card's rendering off a single field. ``missing`` is the ordered list
    of camelCase mandatory-field keys still to fill — the card uses it
    both to show "3 of 7" and to deep-link to the next missing input.
    """

    status: str
    missing: list[str]
    mandatory_total: int
    submitted_at: datetime | None = None
    verified_at: datetime | None = None
    rejected_reason: str | None = None


class MeResponse(CamelModel):
    user_id: str
    email: str
    email_verified_at: datetime | None = None
    business_name: str | None = None
    user_type: str
    status: str
    # True when the active session landed via the temp credential and
    # the user hasn't set a real password yet. The frontend uses this
    # as a hard gate — every protected route redirects to
    # /dashboard/settings/password until the flag clears.
    must_change_password: bool = False
    completion: Completion
    verification: VerificationState
    primary: PrimaryData
    business: BusinessData
    bank: BankData


class IfscLookup(CamelModel):
    ifsc: str
    bank: str
    branch: str
    city: str | None = None
    state: str | None = None
