"""Admin console schemas."""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.modules.verification.schemas import DocOut
from app.shared.schemas import CamelModel, CountryCode, CountryList, TagList, text

# ── Auth ─────────────────────────────────────────────────────────────


class LoginIn(BaseModel):
    email: str
    password: str


class LoginOut(CamelModel):
    email: str


# ── Dashboard ────────────────────────────────────────────────────────


class DashboardStats(CamelModel):
    total_users: int
    total_businesses: int
    draft_businesses: int
    pending_verification_businesses: int
    verified_businesses: int
    rejected_businesses: int
    total_products: int
    recent_signups_24h: int
    stuck_signups: int
    pending_docs: int


class TimelinePoint(CamelModel):
    date: str
    count: int


class StuckUser(CamelModel):
    """A business still in ``draft`` 24h+ after signup (owner shown)."""

    user_id: str
    business_id: str
    email: str
    business_name: str | None
    created_at: datetime
    hours_waiting: int


# ── Verification queue / docs ────────────────────────────────────────


class VerifyQueueRow(CamelModel):
    user_id: str
    business_id: str
    email: str
    full_name: str | None
    position: str | None = None
    phone: str | None = None
    business_name: str | None
    country: str | None
    industry: str | None
    trade_position: str | None
    operating_countries: list[str] | None
    submitted_at: datetime | None
    created_at: datetime
    missing_fields: list[str]
    docs: list[DocOut]


class PendingDocRow(CamelModel):
    doc: DocOut
    user_id: str | None
    business_id: str
    user_email: str | None
    user_business_name: str | None
    user_full_name: str | None
    user_country: str | None


class DocStatusChanged(CamelModel):
    doc_id: str
    status: str


class DocRejectIn(CamelModel):
    reason: str


# ── Users ────────────────────────────────────────────────────────────


class UserRow(CamelModel):
    user_id: str
    business_id: str
    email: str
    business_name: str | None
    full_name: str | None
    status: str  # the business's verification status
    email_verified: bool
    created_at: datetime


class UserList(CamelModel):
    total: int
    items: list[UserRow]


class UserDetail(CamelModel):
    user_id: str
    business_id: str
    role: str
    email: str
    email_verified_at: datetime | None
    business_name: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    profile: dict[str, Any] | None
    business_profile: dict[str, Any] | None
    product_count: int
    docs: list[DocOut]
    verification_submitted_at: datetime | None
    verified_at: datetime | None
    verification_rejected_reason: str | None
    missing_mandatory_fields: list[str]


Pincode = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^(|[1-9][0-9]{5})$")]


class AdminProfilePatch(CamelModel):
    """Person fields (``users``). Only keys present are applied; "" clears."""

    full_name: text(100) | None = None
    phone: text(20) | None = None
    position: text(120) | None = None


class AdminBusinessPatch(CamelModel):
    """Business fields (``businesses``). Only keys present are applied; ""
    clears (except ``country``, which is required)."""

    legal_name: text(200) | None = None
    entity_type: Literal["proprietorship", "partnership", "llp", "private_ltd", "public_ltd", ""] | None = None
    industry: text(120) | None = None
    operating_countries: CountryList | None = None
    website_url: text(300) | None = None
    address_line: text(200) | None = None
    city: text(100) | None = None
    state: text(100) | None = None
    pincode: Pincode | None = None
    country: CountryCode | Literal[""] | None = None
    google_business_url: text(300) | None = None
    facebook_url: text(300) | None = None
    trade_position: Literal["seller", "buyer", "both", ""] | None = None
    seller_type: text(60) | None = None
    export_status: text(40) | None = None
    target_markets: CountryList | None = None
    target_buyer_types: TagList | None = None
    company_introduction: text(5000) | None = None


class UserPatchIn(CamelModel):
    """Admin edit of a user + their business. Unknown keys are ignored.
    Status changes use verify/reject."""

    profile: AdminProfilePatch | None = None
    business_profile: AdminBusinessPatch | None = None


class StatusChanged(CamelModel):
    user_id: str
    business_id: str
    status: str


class UserRejectIn(CamelModel):
    reason: str
    #: Admin's checklist of what failed. Subset of the 7 mandatory profile
    #: field keys (``fullName`` etc.) plus ``doc:<slug>`` tokens for each
    #: cert slot that failed. Each ``doc:*`` picked cascades to the
    #: underlying business_document being marked rejected with the same
    #: reason, so the trader sees "Rejected — replace it" on their slot.
    #: Required: at least one item — a reject with no items leaves the
    #: trader without a resubmit checklist.
    failed_items: list[str] = Field(..., min_length=1)


# ── Country document requirements ────────────────────────────────────

#: Lowercase slug: starts with letter/digit, then letters/digits/underscore/
#: hyphen. Enforced client-side & here, kept portable (not a DB regex).
RequirementSlug = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[a-z0-9][a-z0-9_-]{0,39}$")]


def _safe_url_or_none(v: str | None) -> str | None:
    """Only http:// or https:// URLs are stored. Reject javascript:/data:/ftp:.

    Lower-cases scheme comparison, keeps the rest of the URL as entered.
    """
    if v is None:
        return None
    s = v.strip()
    if not s:
        return None
    scheme = s.split(":", 1)[0].lower() if ":" in s else ""
    if scheme not in ("http", "https"):
        raise ValueError("Help URL must start with http:// or https://.")
    return s


class DocRequirementIn(CamelModel):
    """POST /admin/doc-requirements — create a new catalog entry."""

    country_code: CountryCode  # type: ignore[valid-type]
    slug: RequirementSlug  # type: ignore[valid-type]
    display_name: text(100, 2)  # type: ignore[valid-type]
    description: text(500) | None = None  # type: ignore[valid-type]
    help_url: str | None = Field(default=None, max_length=500)
    is_mandatory: bool = True

    @field_validator("help_url")
    @classmethod
    def _check_help_url(cls, v: str | None) -> str | None:
        return _safe_url_or_none(v)


class DocRequirementUpdate(CamelModel):
    """PATCH /admin/doc-requirements/{id} — edit mutable fields.

    ``country_code`` and ``slug`` are intentionally omitted — changing them
    would orphan every upload tied to the row. Deactivate the old row and
    add a new one if the policy really changed shape.
    """

    display_name: text(100, 2) | None = None  # type: ignore[valid-type]
    description: text(500) | None = None  # type: ignore[valid-type]
    help_url: str | None = Field(default=None, max_length=500)
    is_mandatory: bool | None = None
    is_active: bool | None = None

    @field_validator("help_url")
    @classmethod
    def _check_help_url(cls, v: str | None) -> str | None:
        return _safe_url_or_none(v)


class DocRequirementOut(CamelModel):
    id: str
    country_code: str
    slug: str
    display_name: str
    description: str | None
    help_url: str | None
    is_mandatory: bool
    is_active: bool
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime
