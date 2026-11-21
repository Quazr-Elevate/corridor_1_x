"""Uniqueness of a phone among live users (the phone lives in the vault,
``user_identities``, which holds only live accounts), and the one place a
unique-index violation becomes a 409. Company website uniqueness lives with
the identity vault (``modules/masking``).

Two layers: a friendly pre-check (indexed lookup on the normalized
column), and the UNIQUE indexes themselves — :func:`commit_or_conflict`
turns a racing duplicate's ``IntegrityError`` into the same 409.
"""
from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequest, Conflict, DomainError
from app.modules.masking import service as masking
from app.modules.masking.service import WEBSITE_TAKEN

PHONE_TAKEN = "This phone number can't be used for this account. If it is yours, contact support."

_BY_COLUMN = {
    "phone_normalized": PHONE_TAKEN,
    "website_normalized": WEBSITE_TAKEN,
}


async def ensure_phone_available(db: AsyncSession, user_id: uuid.UUID, phone: str | None) -> None:
    if await masking.phone_taken(db, phone, user_id):
        raise Conflict(PHONE_TAKEN)


#: CHECK constraints a request can trip (normally caught earlier by the
#: schemas) → friendly 400 instead of a 500.
_CHECKS = {
    "ck_products_moq_le_quantity": "MOQ can't be larger than the available quantity.",
    "ck_products_amounts": "Quantity, MOQ and price can't be negative.",
    "ck_products_category": "Unknown product category.",
    "ck_products_unit": "Unit must be MT, kg or quintal.",
    "ck_products_currency": "Currency must be a 3-letter ISO 4217 code.",
    "ck_products_name_length": "Product name must be at least 2 characters.",
    "ck_businesses_trade_position": "Trade position must be seller, buyer or both.",
    "ck_businesses_entity_type": "Unknown entity type.",
    "ck_businesses_country": "Country must be a 2-letter ISO code.",
    "ck_businesses_rejected_has_reason": "A rejection reason is required.",
    "ck_contact_reveals_not_self": "This is your own business's listing — nothing to reveal.",
    "ck_user_identities_email_lowercase": "Email must be lowercase.",
}


def conflict_from_integrity_error(exc: IntegrityError) -> DomainError | None:
    """Map a UNIQUE (→ 409) or CHECK (→ 400) violation to a friendly error."""
    msg = str(exc.orig) if exc.orig is not None else str(exc)
    for column, detail in _BY_COLUMN.items():
        if column in msg:
            return Conflict(detail)
    for name, detail in _CHECKS.items():
        if name in msg:
            return BadRequest(detail)
    return None


async def commit_or_conflict(db: AsyncSession) -> None:
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        conflict = conflict_from_integrity_error(e)
        if conflict is not None:
            raise conflict from None
        raise
