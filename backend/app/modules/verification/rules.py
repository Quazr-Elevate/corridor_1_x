"""Verified-badge rules + state machine.

A business may send its profile for KYB review once it has:

  * the company basics — legal name, registered address (line + city) and
    country (:data:`PROFILE_FIELDS`), and
  * an entry for every **mandatory** KYB document type the admin defined for
    its country (``kyb_document_types.is_mandatory``), carrying the parts
    that type requires (value / file). A rejected entry doesn't count.

Logo, banner and every other profile field are optional. Submission is an
explicit user action (``POST /me/submit-verification``); admins approve or
reject via /admin.

Missing items are reported as stable keys: camelCase field keys
(``addressLine``) and ``kyb:<code>`` for document types (``kyb:gstin``).
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business, BusinessStatus
from app.models.business_document import BusinessDocument, DocStatus
from app.models.country import Country
from app.models.kyb_document_type import KybDocumentType


@dataclass(frozen=True)
class ProfileField:
    """A company field that gates KYB submission. ``key`` is the camelCase
    name the frontend uses."""

    key: str
    label: str
    column: str


PROFILE_FIELDS: tuple[ProfileField, ...] = (
    ProfileField("legalName", "Company name", "legal_name"),
    ProfileField("addressLine", "Registered address", "address_line"),
    ProfileField("city", "City", "city"),
    ProfileField("country", "Country", "country"),
)


@dataclass(frozen=True)
class Requirement:
    key: str
    label: str


@dataclass(frozen=True)
class RequirementsReport:
    missing: list[Requirement]
    total: int


def _is_filled(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple)):
        return len(value) > 0
    return True


def satisfies(entry: BusinessDocument, doc_type: KybDocumentType) -> bool:
    """Does ``entry`` provide what ``doc_type`` asks for?"""
    if entry.status == DocStatus.rejected:
        return False
    if doc_type.needs_value and not entry.has_value:
        return False
    if doc_type.needs_file and not entry.has_file:
        return False
    return entry.has_value or entry.has_file


async def mandatory_types(db: AsyncSession, country: str) -> list[KybDocumentType]:
    return list(
        await db.scalars(
            select(KybDocumentType)
            .where(
                KybDocumentType.country == country,
                KybDocumentType.is_mandatory.is_(True),
                KybDocumentType.active.is_(True),
            )
            .order_by(KybDocumentType.sort_order, KybDocumentType.name)
        )
    )


async def open_countries(db: AsyncSession) -> list[Country]:
    """Countries a business may pick: ``active`` and with at least one
    active, required document type (set up by an admin)."""
    has_required = (
        select(KybDocumentType.country)
        .where(KybDocumentType.is_mandatory.is_(True), KybDocumentType.active.is_(True))
        .distinct()
    )
    return list(
        await db.scalars(
            select(Country).where(Country.active.is_(True), Country.code.in_(has_required)).order_by(Country.name)
        )
    )


async def configured_countries(db: AsyncSession) -> list[str]:
    return sorted(c.code for c in await open_countries(db))


async def is_configured(db: AsyncSession, country: str) -> bool:
    return country.upper() in await configured_countries(db)


async def requirements(db: AsyncSession, business: Business) -> RequirementsReport:
    """What the business still needs before it can submit for KYB."""
    missing = [
        Requirement(f.key, f.label) for f in PROFILE_FIELDS if not _is_filled(getattr(business, f.column))
    ]
    types = await mandatory_types(db, business.country)
    if types:
        entries = {
            e.document_type_id: e
            for e in await db.scalars(
                select(BusinessDocument).where(
                    BusinessDocument.business_id == business.id,
                    BusinessDocument.document_type_id.in_([t.id for t in types]),
                )
            )
        }
        missing += [
            Requirement(f"kyb:{t.code}", t.name)
            for t in types
            if t.id not in entries or not satisfies(entries[t.id], t)
        ]
    return RequirementsReport(missing=missing, total=len(PROFILE_FIELDS) + len(types))


def reopen_review(business: Business) -> bool:
    """A verified business changed something KYB depends on → back to
    ``pending_verification`` so Corridor ops re-checks it. Returns whether
    the status changed. (Its listings leave the market until re-approved.)"""
    if business.verification_status != BusinessStatus.verified:
        return False
    from app.core.time import utcnow

    business.verification_status = BusinessStatus.pending_verification
    business.verified_at = None
    business.verification_submitted_at = utcnow()
    business.verification_rejected_reason = None
    business.verification_rejected_items = None
    return True


#: Statuses an admin may approve from. ``rejected`` is allowed so an admin
#: can overturn their own rejection once the business fixed things.
ADMIN_VERIFIABLE_STATUSES = frozenset({BusinessStatus.pending_verification, BusinessStatus.rejected})

#: Statuses an admin may reject from (``verified`` = revoke the badge).
ADMIN_REJECTABLE_STATUSES = frozenset({BusinessStatus.pending_verification, BusinessStatus.verified})

#: Statuses from which the business may press "Send for verification".
SUBMITTABLE_STATUSES = frozenset({BusinessStatus.draft, BusinessStatus.rejected})
