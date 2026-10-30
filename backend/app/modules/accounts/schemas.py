"""Account schemas — /me and the Passport section saves (Company / Contact /
Business). Required inputs carry length / ``Literal`` constraints so a direct
API call can't persist empty or off-menu values."""

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from app.shared.schemas import CamelModel, CountryCode, CountryList, TagList, text

EntityType = Literal["proprietorship", "partnership", "llp", "private_ltd", "public_ltd"]
TradePosition = Literal["seller", "buyer", "both"]

# ── /me ─────────────────────────────────────────────────────────────


class PrimaryData(CamelModel):
    """The signed-in person (``users``)."""

    full_name: str | None = None
    phone: str | None = None
    position: str | None = None


class BusinessData(CamelModel):
    """The user's business (``businesses``)."""

    legal_name: str | None = None
    entity_type: str | None = None
    industry: str | None = None
    operating_countries: list[str] | None = None
    website_url: str | None = None
    address_line: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    country: str | None = None
    google_business_url: str | None = None
    facebook_url: str | None = None
    trade_position: str | None = None
    seller_type: str | None = None
    export_status: str | None = None
    target_markets: list[str] | None = None
    target_buyer_types: list[str] | None = None
    company_introduction: str | None = None


class VerificationState(CamelModel):
    """The business's Verified-badge state.

    ``status`` is ``businesses.verification_status`` ("draft" |
    "pending_verification" | "verified" | "rejected"). ``missing`` is the
    ordered list of camelCase mandatory-field keys still to fill.
    """

    status: str
    #: Stable keys still to provide: field keys (``addressLine``) and
    #: ``kyb:<code>`` for mandatory document types (``kyb:gstin``).
    missing: list[str]
    #: Human labels, same order as ``missing``.
    missing_labels: list[str] = []
    mandatory_total: int
    submitted_at: datetime | None = None
    verified_at: datetime | None = None
    rejected_reason: str | None = None


class BrandingData(CamelModel):
    """Public images of the business (dashboard hero)."""

    logo_url: str | None = None
    banner_url: str | None = None


class MeResponse(CamelModel):
    user_id: str
    business_id: str
    role: str
    email: str
    email_verified_at: datetime | None = None
    business_name: str | None = None
    #: ISO 4217 — converted prices and filter amounts are shown in this.
    display_currency: str = "USD"
    user_type: str
    status: str
    verification: VerificationState
    primary: PrimaryData
    business: BusinessData
    branding: BrandingData = BrandingData()
    #: True until the user finishes or skips the quick tour.
    show_tour: bool = False


class MeUpdate(CamelModel):
    """PATCH /me — the signed-in person's preferences. Fields are only
    changed when sent."""

    display_currency: text(3, 3) | None = None  # type: ignore[valid-type]
    #: ``true`` = finished or skipped the quick tour; ``false`` = show it again.
    tour_completed: bool | None = None


class BusinessProfileSaveIn(CamelModel):
    """PUT /me/business-profile — company name, registered address and
    country (the KYB document list follows the country). Optional fields are
    only changed when sent."""

    legal_name: text(200, 2)  # type: ignore[valid-type]
    country: CountryCode
    address_line: text(200) | None = None  # type: ignore[valid-type]
    city: text(100) | None = None  # type: ignore[valid-type]
    state: text(100) | None = None  # type: ignore[valid-type]
    pincode: text(10) | None = None  # type: ignore[valid-type]
    website_url: text(300) | None = None  # type: ignore[valid-type]
    entity_type: EntityType | None = None


#: Optional profile fields saved only when present in the payload.
PROFILE_OPTIONAL_FIELDS = ("address_line", "city", "state", "pincode", "entity_type")


class ImageUploaded(CamelModel):
    url: str


# ── Passport section saves ──────────────────────────────────────────


class CompanyInfoIn(CamelModel):
    """Company info → ``businesses``. ``entityType`` is only changed when sent."""

    legal_name: text(200, 2)  # type: ignore[valid-type]
    industry: text(120, 1)  # type: ignore[valid-type]
    operating_countries: CountryList = Field(min_length=1, max_length=60)
    website_url: text(300) | None = None  # type: ignore[valid-type]
    entity_type: EntityType | None = None
    # Company address + socials (docs/04_data_model.md → businesses). Each is
    # only changed when sent, so older clients don't wipe them.
    address_line: text(200) | None = None  # type: ignore[valid-type]
    city: text(100) | None = None  # type: ignore[valid-type]
    state: text(100) | None = None  # type: ignore[valid-type]
    pincode: text(10) | None = None  # type: ignore[valid-type]
    country: CountryCode | None = None
    google_business_url: text(300) | None = None  # type: ignore[valid-type]
    facebook_url: text(300) | None = None  # type: ignore[valid-type]


#: Optional company fields saved only when present in the payload.
COMPANY_OPTIONAL_FIELDS = (
    "address_line",
    "city",
    "state",
    "pincode",
    "google_business_url",
    "facebook_url",
)


class PrimaryContactIn(CamelModel):
    """Primary contact → the signed-in ``users`` row."""

    full_name: text(100, 2)  # type: ignore[valid-type]
    phone: text(20) | None = None  # type: ignore[valid-type]
    position: text(120) | None = None  # type: ignore[valid-type]

    @field_validator("full_name")
    @classmethod
    def _no_digits_in_name(cls, v: str) -> str:
        # Buyers see this name — digits almost always mean a typo.
        if any(ch.isdigit() for ch in v):
            raise ValueError("Full name shouldn't contain digits.")
        return v


class BusinessProfileIn(CamelModel):
    """How the business trades → ``businesses``."""

    trade_position: TradePosition
    seller_type: text(60) | None = None  # type: ignore[valid-type]
    export_status: text(40) | None = None  # type: ignore[valid-type]
    target_markets: CountryList = Field(default_factory=list, max_length=60)
    target_buyer_types: TagList = Field(default_factory=list, max_length=30)
    company_introduction: text(5000) | None = None  # type: ignore[valid-type]


class OnboardingStatus(CamelModel):
    company_info_done: bool
    primary_contact_done: bool
    business_profile_done: bool


class OnboardingSaved(CamelModel):
    ok: bool = True
    status: OnboardingStatus
