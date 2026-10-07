"""Verified-badge rules + state machine.

A Cor1x user earns the ``Verified`` badge once seven mandatory profile
fields are filled AND an admin has approved them. This module owns:

  * the canonical list of the seven fields (so backend, frontend progress
    card, and admin UI stay in sync),
  * the completeness check,
  * the auto-flip from ``active`` → ``pending_verification`` the moment
    the seventh field is saved.

The seven fields are a deliberate minimum — a buyer who messages this
seller today should have enough information to decide whether to reply.
Everything else in the user's profile is bonus and lives below the
verification band in the admin UI.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.models.business_profile import BusinessProfile
from app.models.profile import Profile
from app.models.user import User, UserStatus


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


def _value_for(key: str, profile: Profile | None, business: BusinessProfile | None):
    """Resolve a camelCase mandatory-field key to its live column value."""
    if key in {"fullName", "position", "phone"}:
        if profile is None:
            return None
        return {
            "fullName": profile.full_name,
            "position": profile.position,
            "phone": profile.phone,
        }[key]
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


def missing_mandatory_keys(
    profile: Profile | None,
    business: BusinessProfile | None,
) -> list[str]:
    """Return the camelCase keys of fields still awaiting a value."""
    return [
        f.key
        for f in MANDATORY_FIELDS
        if not _is_filled(_value_for(f.key, profile, business))
    ]


def is_profile_complete(
    profile: Profile | None,
    business: BusinessProfile | None,
) -> bool:
    return not missing_mandatory_keys(profile, business)


#: Statuses from which a 7-field completion legitimately promotes the
#: user to pending_verification. ``signed_up`` is excluded (email not
#: yet verified); ``pending_verification`` already there, idempotent;
#: ``verified`` is a terminal success — don't knock them back on an
#: edit. ``rejected`` is included so a user who fixes their profile
#: after an admin rejection automatically re-enters the queue.
_SUBMITTABLE_STATUSES = frozenset(
    {
        UserStatus.email_verified,
        UserStatus.active,
        UserStatus.rejected,
    }
)


def maybe_submit_for_verification(
    user: User,
    profile: Profile | None,
    business: BusinessProfile | None,
) -> bool:
    """If all seven fields are now filled, enter the admin review queue.

    Called at the end of every profile-mutating request. Idempotent —
    users already pending or verified are left alone so a late edit
    doesn't shuffle a verified user back into the queue, and a user
    sitting in review doesn't get a fresh ``submitted_at`` on every
    save. A rejected user whose edit filled the missing fields IS
    re-submitted (that's the "fix & auto-resubmit" loop).

    Returns ``True`` when the status flipped.
    """
    if user.status not in _SUBMITTABLE_STATUSES:
        return False
    if not is_profile_complete(profile, business):
        return False
    user.status = UserStatus.pending_verification
    user.verification_submitted_at = datetime.now(tz=timezone.utc)
    # Clear any stale admin note from a previous rejected cycle so the
    # user doesn't see an old reason on their next login.
    user.verification_rejected_reason = None
    return True
