"""Admin console schemas."""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field, BaseModel, StringConstraints

from app.modules.verification.schemas import DocOut
from app.shared.schemas import CamelModel, CountryCode, CountryList, TagList, text

# ── Auth ─────────────────────────────────────────────────────────────


class LoginIn(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)


class LoginOut(CamelModel):
    """The signed-in admin (/admin/login, /admin/me)."""

    id: str
    email: str
    full_name: str
    role: str
    permissions: list[str]
    must_change_password: bool


class AdminChangePasswordIn(CamelModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=12, max_length=72)


# ── Admin accounts (super admin) ─────────────────────────────────────

AdminRoleName = Literal["super_admin", "reviewer"]


class AdminAccountOut(CamelModel):
    id: str
    email: str
    full_name: str
    role: AdminRoleName
    status: Literal["active", "disabled"]
    must_change_password: bool
    lock_state: Literal["none", "temporary", "support"]
    last_login_at: datetime | None
    created_by: str
    created_at: datetime


class AdminCreateIn(CamelModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, max_length=200,
                                            pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
    full_name: text(100, 2)  # type: ignore[valid-type]
    role: AdminRoleName


class AdminPatchIn(CamelModel):
    full_name: text(100, 2) | None = None  # type: ignore[valid-type]
    role: AdminRoleName | None = None
    status: Literal["active", "disabled"] | None = None


class AdminWithPassword(CamelModel):
    """Create / reset-password response — the temporary password is shown
    once and never stored in plain form."""

    admin: AdminAccountOut
    temporary_password: str


class SessionOut(CamelModel):
    created_at: datetime
    last_seen_at: datetime
    ip_prefix: str | None = None
    user_agent: str | None = None


class AccountSecurityOut(CamelModel):
    """Trader sign-in state shown on the admin user page."""

    lock_state: Literal["none", "temporary", "support"]
    locked_until: datetime | None = None
    failed_login_count: int
    active_session: SessionOut | None = None
    last_login_at: datetime | None = None


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
    business_name: str | None
    country: str | None
    industry: str | None
    trade_position: str | None
    operating_countries: list[str] | None
    submitted_at: datetime | None
    created_at: datetime
    missing_fields: list[str]
    docs: list[DocOut]
    #: "submitted" — sent for KYB; "documents" — a verified business added or
    #: changed documents that still need a look.
    review_kind: str = "submitted"
    status: str = "pending_verification"


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
    verification_rejected_items: list[str] = []
    missing_mandatory_fields: list[str]
    security: AccountSecurityOut | None = None


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
    #: What failed: profile field keys (``addressLine``) and KYB entries
    #: (``kyb:<code>`` / ``doc:<entry id>``). Flagged entries are rejected
    #: with the same reason.
    failed_items: list[str] = Field(min_length=1, max_length=60)
