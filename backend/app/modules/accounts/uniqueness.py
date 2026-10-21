"""Uniqueness of phone (users) / legal company name / website (businesses)
among LIVE rows (the UNIQUE indexes are partial: WHERE deleted_at IS NULL).

Two layers: a friendly pre-check (indexed lookup on the normalized
column), and the UNIQUE indexes themselves — :func:`commit_or_conflict`
turns a racing duplicate's ``IntegrityError`` into the same 409.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequest, Conflict, DomainError
from app.models.business import Business
from app.models.user import User
from app.shared.normalize import normalize_legal_name, normalize_phone, normalize_website

PHONE_TAKEN = "This phone number is already registered on Cor1x."
LEGAL_NAME_TAKEN = "This legal company name is already registered on Cor1x."
WEBSITE_TAKEN = "This website is already linked to another Cor1x account."

_BY_COLUMN = {
    "phone_normalized": PHONE_TAKEN,
    "legal_name_normalized": LEGAL_NAME_TAKEN,
    "website_normalized": WEBSITE_TAKEN,
}


async def ensure_phone_available(db: AsyncSession, user_id: uuid.UUID, phone: str | None) -> None:
    key = normalize_phone(phone)
    if key is None:
        return
    other = await db.scalar(select(User.id).where(User.phone_normalized == key, User.id != user_id, User.deleted_at.is_(None)))
    if other is not None:
        raise Conflict(PHONE_TAKEN)


async def ensure_company_available(
    db: AsyncSession,
    business_id: uuid.UUID,
    *,
    legal_name: str | None = None,
    website_url: str | None = None,
) -> None:
    name_key = normalize_legal_name(legal_name)
    if name_key is not None:
        other = await db.scalar(
            select(Business.id).where(
                Business.legal_name_normalized == name_key, Business.id != business_id, Business.deleted_at.is_(None)
            )
        )
        if other is not None:
            raise Conflict(LEGAL_NAME_TAKEN)
    site_key = normalize_website(website_url)
    if site_key is not None:
        other = await db.scalar(
            select(Business.id).where(
                Business.website_normalized == site_key, Business.id != business_id, Business.deleted_at.is_(None)
            )
        )
        if other is not None:
            raise Conflict(WEBSITE_TAKEN)


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
    "ck_users_email_lowercase": "Email must be lowercase.",
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
