"""Passport section-completeness predicates — single source for /me,
onboarding status and admin views."""
from __future__ import annotations

from app.models.business import Business
from app.models.business_identity import BusinessIdentity
from app.models.user import User
from app.models.user_identity import UserIdentity


def company_info_done(b: Business | None, identity: BusinessIdentity | None) -> bool:
    return bool(b and identity and identity.legal_name and b.industry and b.operating_countries)


def primary_contact_done(u: User | None, person: UserIdentity | None) -> bool:
    return bool(u and person and person.full_name and u.position)


def business_profile_done(b: Business | None) -> bool:
    return bool(b and b.trade_position)
