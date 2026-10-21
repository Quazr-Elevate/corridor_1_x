"""Verified-badge rules + state machine.

A Cor1x business earns the ``Verified`` badge once seven mandatory fields
are filled AND an admin has approved it. This module owns:

  * the canonical list of the seven fields (so backend, frontend progress
    card, and admin UI stay in sync),
  * the completeness check.

Submission into the admin queue is an explicit user action
(``POST /me/submit-verification``); admins approve/reject via /admin.

The seven fields are a deliberate minimum — a buyer who messages this
seller today should have enough information to decide whether to reply.
Everything else in the user's profile is bonus and lives below the
verification band in the admin UI.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models.business import Business, BusinessStatus
from app.models.user import User


@dataclass(frozen=True)
class MandatoryField:
    """One of the seven fields that gates the Verified badge.

    ``key`` is the camelCase identifier the frontend uses (so the
    ``VerificationProgress`` card and the admin audit list can agree on a
    stable name without the Python/TS case translation drifting).
    ``section`` tells the UI which tab + anchor to deep-link to.
    """

    key: str
    label: str
    section: str  # "profile" | "company" | "business"
    anchor: str   # URL fragment to scroll into view


# Order matters — the progress card walks this list top-to-bottom to find
# the next missing field, so putting the quickest wins first (name,
# phone) keeps the first "finish →" click short.
MANDATORY_FIELDS: tuple[MandatoryField, ...] = (
    MandatoryField("fullName",            "Full name",            "profile",  "full-name"),
    MandatoryField("position",            "Position / role",      "profile",  "position"),
    MandatoryField("phone",               "Phone number",         "profile",  "phone"),
    MandatoryField("legalName",           "Legal company name",   "company",  "legal-name"),
    MandatoryField("industry",            "Industry",             "company",  "industry"),
    MandatoryField("operatingCountries",  "Operating countries",  "company",  "operating-countries"),
    MandatoryField("tradePosition",       "Trade position",       "business", "trade-position"),
)


def _value_for(key: str, owner: User | None, business: Business | None):
    """Resolve a camelCase mandatory-field key to its live column value.
    Person fields come from the business owner (``users``), company fields
    from ``businesses``."""
    if key in {"fullName", "position", "phone"}:
        if owner is None:
            return None
        return {"fullName": owner.full_name, "position": owner.position, "phone": owner.phone}[key]
    if business is None:
        return None
    return {
        "legalName": business.legal_name,
        "industry": business.industry,
        "operatingCountries": business.operating_countries,
        "tradePosition": business.trade_position,
    }[key]


def _is_filled(value) -> bool:
    """Treat empty strings, empty arrays, and None as "not filled"."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple)):
        return len(value) > 0
    return True


def missing_mandatory_keys(owner: User | None, business: Business | None) -> list[str]:
    """Return the camelCase keys of fields still awaiting a value."""
    return [f.key for f in MANDATORY_FIELDS if not _is_filled(_value_for(f.key, owner, business))]


#: Statuses an admin may approve from. ``rejected`` is allowed so an admin
#: can overturn their own rejection once the business fixed things.
ADMIN_VERIFIABLE_STATUSES = frozenset({BusinessStatus.pending_verification, BusinessStatus.rejected})

#: Statuses an admin may reject from (``verified`` = revoke the badge).
ADMIN_REJECTABLE_STATUSES = frozenset({BusinessStatus.pending_verification, BusinessStatus.verified})

#: Statuses from which the business may press "Send for verification".
SUBMITTABLE_STATUSES = frozenset({BusinessStatus.draft, BusinessStatus.rejected})
