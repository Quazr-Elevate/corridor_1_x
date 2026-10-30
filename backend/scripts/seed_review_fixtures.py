"""Seed fully-filled test users ready for admin review.

Creates N test accounts whose business has:
  * all 7 mandatory profile fields filled
  * one business_registration cert uploaded for their country
  * verification_status = pending_verification

so they appear in the admin Docs → Business certificate tab for the
single-review flow. Idempotent: re-running updates existing fixtures by
email instead of creating duplicates.

Run with the uvicorn env active:

    cd backend
    .\\.venv\\Scripts\\python.exe -m scripts.seed_review_fixtures

Each account gets the password ``TestPass123!``.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.integrations.storage import configure_storage
from app.integrations.storage.local import LocalStorage
from app.models.business import Business, BusinessStatus
from app.models.business_document import BusinessDocument, DocStatus
from app.models.business_document_requirement import BusinessDocumentRequirement
from app.models.user import AccountStatus, User, UserRole

PASSWORD = "TestPass123!"
TERMS_VERSION = "1"

# One tiny valid 1x1 PNG — plenty for admin to see the file type + preview.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6368606000000000050001a5a5a90a0000000049454e44ae426082"
)

FIXTURES = [
    {
        "email": "review1@review.cor1x.co",
        "full_name": "Priya Sharma",
        "position": "Export Manager",
        "phone": "+91 98100 11111",
        "country": "IN",
        "legal_name": "Sharma Commodities Pvt Ltd",
        "industry": "Rice",
        "operating_countries": ["IN", "AE"],
        "trade_position": "seller",
    },
    {
        "email": "review2@review.cor1x.co",
        "full_name": "Rohan Mehta",
        "position": "CEO",
        "phone": "+91 98200 22222",
        "country": "IN",
        "legal_name": "Mehta AgriFoods LLP",
        "industry": "Spices",
        "operating_countries": ["IN"],
        "trade_position": "both",
    },
    {
        "email": "review3@review.cor1x.co",
        "full_name": "Ahmed Al-Rashid",
        "position": "Procurement Head",
        "phone": "+971 50 123 4567",
        "country": "AE",
        "legal_name": "Al-Rashid Trading FZE",
        "industry": "Pulses",
        "operating_countries": ["AE", "SA", "OM"],
        "trade_position": "buyer",
    },
]


async def _upsert(session, fixture: dict) -> None:
    email = fixture["email"].lower()
    now = datetime.now(tz=timezone.utc)

    user = (await session.scalars(select(User).where(User.email == email))).one_or_none()
    if user is None:
        business = Business(
            country=fixture["country"],
            operating_countries=fixture["operating_countries"],
            legal_name=fixture["legal_name"],
            industry=fixture["industry"],
            trade_position=fixture["trade_position"],
            verification_status=BusinessStatus.pending_verification,
            verification_submitted_at=now,
        )
        user = User(
            business=business,
            role=UserRole.owner,
            email=email,
            password_hash=hash_password(PASSWORD),
            account_status=AccountStatus.active,
            email_verified_at=now,
            full_name=fixture["full_name"],
            position=fixture["position"],
            phone=fixture["phone"],
            session_version=0,
            consent_at=now,
            consent_version=TERMS_VERSION,
            last_login_at=now,
        )
        session.add_all([business, user])
        print(f"[new]     {email}  ({fixture['legal_name']})")
    else:
        business = user.business
        user.full_name = fixture["full_name"]
        user.position = fixture["position"]
        user.phone = fixture["phone"]
        business.country = fixture["country"]
        business.operating_countries = fixture["operating_countries"]
        business.legal_name = fixture["legal_name"]
        business.industry = fixture["industry"]
        business.trade_position = fixture["trade_position"]
        business.verification_status = BusinessStatus.pending_verification
        business.verification_submitted_at = business.verification_submitted_at or now
        business.verification_rejected_reason = None
        business.verification_rejected_items = None
        print(f"[refresh] {email}  ({fixture['legal_name']})")

    await session.flush()

    # Mandatory business_registration doc for this country, if the catalog has one.
    req = (
        await session.scalars(
            select(BusinessDocumentRequirement)
            .where(BusinessDocumentRequirement.country_code == fixture["country"])
            .where(BusinessDocumentRequirement.slug == "business_registration")
            .where(BusinessDocumentRequirement.is_active.is_(True))
        )
    ).one_or_none()
    if req is None:
        print(f"  ! no business_registration requirement for {fixture['country']} — skipping doc")
        return

    existing = (
        await session.scalars(
            select(BusinessDocument)
            .where(BusinessDocument.business_id == business.id)
            .where(BusinessDocument.required_doc_type_id == req.id)
        )
    ).all()
    if existing:
        print(f"  = cert already on file ({len(existing)} row)")
        return

    key = f"verification/{business.id}/{uuid.uuid4().hex}.png"
    # Store on local disk (dev storage default). Avoids importing the full
    # storage layer by writing straight to the path the local backend expects.
    from app.integrations.storage import get_storage
    await get_storage().save(TINY_PNG, key, "image/png")

    doc = BusinessDocument(
        business_id=business.id,
        uploaded_by_user_id=user.id,
        required_doc_type_id=req.id,
        doc_type="business_registration",
        original_filename="business-registration.png",
        storage_key=key,
        mime_type="image/png",
        size_bytes=len(TINY_PNG),
        status=DocStatus.pending,
        uploaded_at=now,
    )
    session.add(doc)
    print(f"  + cert uploaded ({len(TINY_PNG)} bytes)")


async def main() -> None:
    # Scripts don't go through app.main.lifespan, so configure storage
    # ourselves — same local path the uvicorn backend uses.
    configure_storage(LocalStorage(settings.storage_path))
    async with SessionLocal() as session:
        for fixture in FIXTURES:
            await _upsert(session, fixture)
        await session.commit()
    print(f"\nDone. Login with any of:")
    for f in FIXTURES:
        print(f"  {f['email']}  /  {PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())
