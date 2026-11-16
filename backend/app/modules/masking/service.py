"""The one door to the identity vault (build plan 18.1–18.3).

``business_identities`` holds a company's name, address and website. Every
other module holds ``businesses.company_code`` and comes here when it needs
more:

* a business reading or editing **its own** identity — :func:`own_identity`;
* staff reading someone's identity — :func:`unmask_for_staff` (audited as
  ``identity.unmasked``, rate-limited, with an alert on volume) and
  :func:`names_for_staff` for the lists a reviewer works from.

Nothing here returns an identity to another business. Until deals exist (M3)
there is no trader-to-trader unmask at all.
"""
from __future__ import annotations

import logging
import secrets
import uuid
from typing import Protocol

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from app.core.errors import Conflict, NotFound
from app.core.time import utcnow
from app.models.admin_action import AdminAction
from app.models.business import Business
from app.models.business_identity import VAULT_COLUMNS, BusinessIdentity
from app.ratelimit import RateLimitRule, get_limiter
from app.shared.normalize import normalize_legal_name, normalize_website

log = logging.getLogger(__name__)

LEGAL_NAME_TAKEN = "This legal company name is already registered on Cor1x."
WEBSITE_TAKEN = "This website is already linked to another Cor1x account."

#: Hard ceiling on identities one admin can open in an hour.
STAFF_UNMASK = RateLimitRule("identity.unmask:admin", limit=120, window_sec=60 * 60)
#: Past this many in an hour the access is still allowed, and flagged.
STAFF_UNMASK_ALERT = RateLimitRule("identity.unmask_alert:admin", limit=40, window_sec=60 * 60)
#: One alert row per admin per hour, however far past the line they go.
_ALERT_SENT = RateLimitRule("identity.unmask_alert_sent:admin", limit=1, window_sec=60 * 60)
#: Pages of names (queues, the directory) an admin can load in an hour.
STAFF_NAME_LISTS = RateLimitRule("identity.list:admin", limit=600, window_sec=60 * 60)

CODE_DIGITS = 6
_CODE_ATTEMPTS = 8


class Staff(Protocol):
    """Who is asking — an ``AdminPrincipal``."""

    id: uuid.UUID
    email: str


# ── A business and its own identity ──────────────────────────────────


async def own_identity(db: AsyncSession, business_id: uuid.UUID) -> BusinessIdentity:
    """The vault row of the caller's own business, created empty on first
    use. Not an unmask: a company reading itself."""
    identity = await db.get(BusinessIdentity, business_id)
    if identity is None:
        identity = BusinessIdentity(business_id=business_id)
        db.add(identity)
    return identity


def start_identity(db: AsyncSession, business_id: uuid.UUID, *, legal_name: str) -> BusinessIdentity:
    """The vault row of a business that is being created at sign-up."""
    identity = BusinessIdentity(business_id=business_id, legal_name=legal_name)
    db.add(identity)
    return identity


def company_field(business: Business, identity: BusinessIdentity, column: str):
    """A company profile column, wherever it lives."""
    return getattr(identity if column in VAULT_COLUMNS else business, column)


def set_company_field(business: Business, identity: BusinessIdentity, column: str, value) -> None:
    setattr(identity if column in VAULT_COLUMNS else business, column, value)


async def ensure_company_available(
    db: AsyncSession,
    business_id: uuid.UUID,
    *,
    legal_name: str | None = None,
    website_url: str | None = None,
) -> None:
    """Friendly pre-check for the two UNIQUE indexes on the vault; a racing
    duplicate still hits the index and becomes the same 409."""
    name_key = normalize_legal_name(legal_name)
    if name_key is not None and await _taken(db, BusinessIdentity.legal_name_normalized == name_key, business_id):
        raise Conflict(LEGAL_NAME_TAKEN)
    site_key = normalize_website(website_url)
    if site_key is not None and await _taken(db, BusinessIdentity.website_normalized == site_key, business_id):
        raise Conflict(WEBSITE_TAKEN)


async def _taken(db: AsyncSession, clause: ColumnElement[bool], business_id: uuid.UUID) -> bool:
    other = await db.scalar(
        select(BusinessIdentity.business_id).where(clause, BusinessIdentity.business_id != business_id)
    )
    return other is not None


async def erase(db: AsyncSession, business_id: uuid.UUID) -> None:
    """Delete the vault row (right to erasure). The company code stays on the
    business so history keyed on it still reads, and is never issued again."""
    await db.execute(delete(BusinessIdentity).where(BusinessIdentity.business_id == business_id))


async def identity_for_contact_reveal(db: AsyncSession, seller_business_id: uuid.UUID) -> BusinessIdentity:
    """The seller identity the old contact reveal hands a buyer. Only reached
    while ``CONTACT_REVEAL_ENABLED`` is on; goes away with the reveal code
    (CX-083)."""
    return await own_identity(db, seller_business_id)


# ── Company codes ────────────────────────────────────────────────────


def new_code(country: str) -> str:
    """``IN-482913``: the country and six random digits. Random so a code
    says nothing about when a company joined or how many there are."""
    number = secrets.randbelow(10**CODE_DIGITS)
    return f"{country.upper()}-{number:0{CODE_DIGITS}d}"


async def business_by_code(db: AsyncSession, company_code: str) -> Business:
    """The live business a code belongs to; an unknown code is a 404."""
    business = await db.scalar(
        select(Business).where(Business.company_code == company_code.strip().upper(), Business.deleted_at.is_(None))
    )
    if business is None:
        raise NotFound("No company has that code.")
    return business


async def assign_code(db: AsyncSession, business: Business) -> str:
    """Give a business its code the first time it is verified. A business
    that already has one keeps it for life, whatever happens to its status."""
    if business.company_code:
        return business.company_code
    for _ in range(_CODE_ATTEMPTS):
        code = new_code(business.country)
        if await db.scalar(select(Business.id).where(Business.company_code == code)) is None:
            business.company_code = code
            return code
    raise Conflict("Could not issue a company code. Try again.")


# ── Staff access ─────────────────────────────────────────────────────


async def unmask_for_staff(
    db: AsyncSession,
    staff: Staff,
    business_id: uuid.UUID,
    *,
    purpose: str,
    reason: str | None = None,
) -> BusinessIdentity:
    """A company's identity for one admin, staged with its audit row in the
    caller's transaction. ``purpose`` names the screen (``kyb_review``,
    ``directory``); ``reason`` is the admin's own words where one is asked."""
    await get_limiter().check(STAFF_UNMASK, str(staff.id))
    business = await db.get(Business, business_id)
    if business is None:
        raise NotFound("Business not found.")
    identity = await own_identity(db, business_id)
    _audit(db, staff, "identity.unmasked", business_id, reason, {"purpose": purpose, "company_code": business.company_code})
    await _flag_volume(db, staff)
    return identity


async def names_for_staff(db: AsyncSession, staff: Staff, business_ids: list[uuid.UUID]) -> dict[uuid.UUID, str | None]:
    """Legal names for a page of an admin list. Each page counts against the
    admin's hourly budget; opening a company is what writes an audit row."""
    await get_limiter().check(STAFF_NAME_LISTS, str(staff.id))
    if not business_ids:
        return {}
    rows = await db.execute(
        select(BusinessIdentity.business_id, BusinessIdentity.legal_name).where(
            BusinessIdentity.business_id.in_(business_ids)
        )
    )
    return {business_id: name for business_id, name in rows}


def name_matches(pattern: str) -> ColumnElement[bool]:
    """Clause for the admin directory search: businesses whose legal name
    matches ``pattern`` (an ILIKE pattern)."""
    return Business.id.in_(
        select(BusinessIdentity.business_id).where(BusinessIdentity.legal_name.ilike(pattern))
    )


async def _flag_volume(db: AsyncSession, staff: Staff) -> None:
    """Volume is the signal of misuse (plan 18.3): past the alert line, log
    it and leave one ``identity.bulk_access`` row per hour for the reviewer
    of the audit log."""
    limiter = get_limiter()
    if (await limiter.hit(STAFF_UNMASK_ALERT, str(staff.id))).allowed:
        return
    if not (await limiter.hit(_ALERT_SENT, str(staff.id))).allowed:
        return
    log.warning("identity_bulk_access admin=%s threshold=%s window_sec=%s", staff.id, STAFF_UNMASK_ALERT.limit, STAFF_UNMASK_ALERT.window_sec)
    _audit(
        db, staff, "identity.bulk_access", staff.id, None,
        {"threshold": STAFF_UNMASK_ALERT.limit, "window_sec": STAFF_UNMASK_ALERT.window_sec},
        target_type="admin_user",
    )


def _audit(
    db: AsyncSession,
    staff: Staff,
    action: str,
    target_id: uuid.UUID,
    reason: str | None,
    details: dict,
    *,
    target_type: str = "business",
) -> None:
    db.add(
        AdminAction(
            admin_email=staff.email,
            admin_user_id=staff.id,
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            reason=reason,
            details=details,
            created_at=utcnow(),
        )
    )
