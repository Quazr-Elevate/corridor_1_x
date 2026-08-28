"""Seed a handful of verified sellers + products for the public catalog.

Idempotent — safe to re-run. Skips rows that already exist by mobile.
Not called on startup; run manually with:

    cd backend && .venv/bin/python -m scripts.seed_demo

The point is to have SOMETHING in /public/products while we finish
manual onboarding UX. Ships a mix of rice varieties across states so
the filter chips have signal.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal
from app.models.business_profile import BusinessProfile, OnboardingPath
from app.models.identity import Identity
from app.models.product import Product
from app.models.profile import Profile
from app.models.user import User, UserStatus

# 6 verified sellers x 2-3 products each = ~15 catalog cards, enough
# to see filter behavior. Compact tuple form so this file stays skimmable.
#
# (mobile, full_name, city, state, company, gstin, pan, [products])
_SEED: list[tuple] = [
    (
        "9000000001",
        "Ramesh Kumar",
        "Karnal",
        "Haryana",
        "Kaveri Foods Pvt Ltd",
        "06AABCV1234K1Z5",
        "AABCV1234K",
        [
            ("1121 Steam Basmati", "Rice", "1121", "Haryana", "Jute", 500, 25, Decimal("72.00"), "Aromatic long-grain, 2024 crop."),
            ("Pusa Sella Rice",     "Rice", "Pusa", "Haryana", "PP woven", 300, 50, Decimal("64.00"), "Parboiled Pusa, mill-fresh."),
        ],
    ),
    (
        "9000000002",
        "Vishnu Agrawal",
        "Amritsar",
        "Punjab",
        "Vishnu Rice Mills",
        "03AABCU5678L1Z1",
        "AABCU5678L",
        [
            ("Sharbati Basmati",    "Rice", "Sharbati", "Punjab", "Jute", 200, 25, Decimal("58.50"), "Medium-grain aromatic."),
            ("Sona Masoori",        "Rice", "Sona Masoori", "Andhra Pradesh", "PP woven", 800, 100, Decimal("42.00"), "Short-grain non-basmati."),
            ("1401 Basmati",        "Rice", "1401", "Punjab", "Jute", 150, 25, Decimal("68.00"), "Long-grain export grade."),
        ],
    ),
    (
        "9000000003",
        "Priya Nair",
        "Kochi",
        "Kerala",
        "Nair Spice & Grain",
        "32AABCP9012K1Z3",
        "AABCP9012K",
        [
            ("Matta Rice",          "Rice", "Rosematta", "Kerala", "PP woven", 400, 50, Decimal("48.00"), "Kerala red rice, parboiled."),
            ("Kaima Rice",          "Rice", "Kaima", "Kerala", "PP woven", 250, 50, Decimal("62.00"), "Fine-grain traditional variety."),
        ],
    ),
    (
        "9000000004",
        "Karthik Reddy",
        "Vijayawada",
        "Andhra Pradesh",
        "Reddy Agro Exports",
        "37AABCK3456N1Z9",
        "AABCK3456N",
        [
            ("HMT Rice",            "Rice", "HMT", "Andhra Pradesh", "PP woven", 1200, 100, Decimal("38.00"), "Everyday HMT, sortex clean."),
            ("BPT Sona Masoori",    "Rice", "BPT-5204", "Andhra Pradesh", "Bulk", 2000, 500, Decimal("35.00"), "Bulk-grade, sortex."),
        ],
    ),
    (
        "9000000005",
        "Vikram Nair",
        "Chennai",
        "Tamil Nadu",
        "TN Agro Exports",
        "33AABCT7890P1Z2",
        "AABCT7890P",
        [
            ("Ponni Rice",          "Rice", "Ponni", "Tamil Nadu", "PP woven", 600, 100, Decimal("40.00"), "Boiled ponni, table quality."),
            ("Idli Rice",           "Rice", "Idli", "Tamil Nadu", "PP woven", 400, 50, Decimal("45.00"), "Coarse, ferments well."),
        ],
    ),
    (
        "9000000006",
        "Sanjay Patel",
        "Ahmedabad",
        "Gujarat",
        "Patel Grains",
        "24AABCP4567G1Z0",
        "AABCP4567G",
        [
            ("Tur Dal",             "Pulses", "Tur", "Gujarat", "PP woven", 500, 50, Decimal("110.00"), "Deshelled tur, clean."),
            ("Sugar (M-30)",        "Sugar", "M-30", "Gujarat", "PP woven", 5000, 500, Decimal("38.00"), "Refined mill sugar."),
        ],
    ),
]


async def _get_or_create_seller(session, seed_row) -> User:
    mobile, full_name, city, state, company, gstin, pan, _products = seed_row

    existing = await session.scalar(
        select(Identity).where(Identity.value == mobile)
    )
    if existing:
        user = await session.get(User, existing.user_id)
        # Force back to verified in case admin toggled it during testing.
        if user and user.status != UserStatus.verified:
            user.status = UserStatus.verified
        return user

    user = User(status=UserStatus.verified)
    session.add(user)
    await session.flush()

    session.add(
        Identity(
            user_id=user.id,
            value=mobile,
            verified_at=datetime.now(tz=timezone.utc),
        )
    )
    session.add(
        Profile(
            user_id=user.id,
            full_name=full_name,
            email=f"{mobile}@seed.cor1x.local",
            city=city,
            state=state,
            country="India",
            consent_at=datetime.now(tz=timezone.utc),
            consent_version="T-2026-08-29",
        )
    )
    session.add(
        BusinessProfile(
            user_id=user.id,
            onboarding_path=OnboardingPath.gstin,
            gstin=gstin,
            pan=pan,
            company_name=company,
            business_type="Private Limited Company",
            nature_of_business="Wholesale, Exporter",
            # Bank filled with placeholder so the "verified" gate is satisfied
            # end-to-end (Sprint 2 doesn't actually payout).
            bank_account_number=f"111000{mobile[-4:]}",
            bank_ifsc="HDFC0001234",
            bank_holder_name=company,
            bank_branch_name="Main",
            bank_name="HDFC Bank",
        )
    )
    return user


async def _ensure_products(session, user: User, products: list[tuple]) -> int:
    """Add any product whose name isn't already on this seller."""
    existing = {
        p.name
        for p in await session.scalars(
            select(Product).where(Product.user_id == user.id)
        )
    }
    added = 0
    for (
        name, category, variety, origin_state, packaging,
        quantity, moq, price, description,
    ) in products:
        if name in existing:
            continue
        session.add(
            Product(
                user_id=user.id,
                name=name,
                category=category,
                variety=variety,
                origin_state=origin_state,
                packaging=packaging,
                quantity=Decimal(quantity),
                unit="MT",
                moq=Decimal(moq),
                price_per_unit=price,
                description=description,
                photos=["/uploads/products/placeholder.jpg"],
            )
        )
        added += 1
    return added


async def main() -> None:
    async with SessionLocal() as session:
        total_sellers = 0
        total_products = 0
        for row in _SEED:
            user = await _get_or_create_seller(session, row)
            total_products += await _ensure_products(session, user, row[7])
            total_sellers += 1
        await session.commit()
        print(f"seeded {total_sellers} sellers, added {total_products} new products")


if __name__ == "__main__":
    asyncio.run(main())
