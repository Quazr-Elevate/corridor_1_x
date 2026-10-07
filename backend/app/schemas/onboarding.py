"""Schemas for the 3-step onboarding wizard (Company / Contact / Business).

Required inputs carry ``min_length`` / ``Literal`` constraints so a direct
API call can't persist an empty string or an off-menu enum value — the UI
already blocks these, but we want the invariant to hold whichever
client calls the endpoint.
"""

from typing import Literal

from pydantic import Field, field_validator

from app.schemas.base import CamelModel


class CompanyInfoIn(CamelModel):
    """Step 1 — Company info."""

    legal_name: str = Field(min_length=2, max_length=200)
    industry: str = Field(min_length=1, max_length=120)
    operating_countries: list[str] = Field(min_length=1)
    website_url: str | None = None


class PrimaryContactIn(CamelModel):
    """Step 2 — Primary contact."""

    full_name: str = Field(min_length=2, max_length=100)
    phone: str | None = None
    department: str | None = None
    position: str | None = None

    @field_validator("full_name")
    @classmethod
    def _no_digits_in_name(cls, v: str) -> str:
        # Buyers see this name — numbers in it almost always indicate a
        # typo (the person typed their phone into the wrong field) and
        # buyers will skip over it. Reject early.
        if any(ch.isdigit() for ch in v):
            raise ValueError("Full name shouldn't contain digits.")
        return v


class BusinessProfileIn(CamelModel):
    """Step 3 — Business intent."""

    # Keep the enum values aligned with the three cards on the account
    # page. The UI only ever offers these three — reject anything else
    # so a stray value never pollutes analytics or the match engine.
    trade_position: Literal["seller", "buyer", "both"]
    seller_type: str | None = None
    business_role: str | None = None
    export_status: str | None = None
    target_markets: list[str] = []
    target_buyer_types: list[str] = []
    main_objective: str | None = None
    company_introduction: str | None = None


class OnboardingStatus(CamelModel):
    company_info_done: bool
    primary_contact_done: bool
    business_profile_done: bool
    onboarded_at: str | None = None


class OnboardingSaved(CamelModel):
    ok: bool = True
    status: OnboardingStatus
