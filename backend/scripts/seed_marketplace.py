"""Seed verified buyers and sellers, with live listings, for the test
environment. Not called on startup. Idempotent: people are matched by email
and listings by name, so a second run changes nothing.

    python scripts/seed_marketplace.py

* Four Indian sellers (rice, spices, pulses, sugar and wheat), each with two
  complete, published listings: price range, validity, incoterms, port,
  capacity and lead time, so they appear in the market and can be matched to
  a buyer's request.
* Four buyers: three in the UAE, one in India.
* Every business is verified, has a company code, and gets test credits
  (100 for a buyer, 50 for a seller) so requests and offers can be tried.

The companies and people are made up. Everyone shares one password, printed
at the end. Test data only: never run this against a live database.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.core.time import utcnow  # noqa: E402
from app.main import configure_integrations  # noqa: E402
from app.models.business import Business, BusinessStatus  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.models.user import AccountStatus, User, UserRole  # noqa: E402
from app.modules.credits.service import _post as post_credits  # noqa: E402
from app.modules.fx.service import recompute_price_usd  # noqa: E402
from app.modules.masking import service as masking  # noqa: E402
from seed_demo import photo_for  # noqa: E402

PASSWORD = "Corridor@2026"
SELLER_CREDITS = 50
BUYER_CREDITS = 100

# Listing: (name, category, variety, grade, hs code, origin state, packaging,
#   quantity MT, moq MT, capacity MT/month, lead days, price min, price max USD/MT,
#   port of loading, description)
SELLERS: list[dict] = [
    dict(
        email="anil@kaveriagro.demo", full_name="Anil Gowda", phone="+91 98450 11001",
        company="Kaveri Agro Exports Pvt Ltd", entity_type="private_ltd", industry="Rice milling and export",
        address="Plot 14, Hebbal Industrial Area", city="Mysuru", state="Karnataka", pincode="570016",
        intro="Rice mill exporting non-basmati and basmati rice to the Gulf since 2009.",
        listings=[
            ("Sona Masoori Raw Rice", "Rice", "Sona Masoori", "Premium", "100630", "Karnataka", "PP woven",
             800, 25, 300, 21, "620.00", "680.00", "Chennai",
             "Aged 12 months, sortexed, 5% broken max. Lightweight grain popular for daily meals."),
            ("1121 Steam Basmati Rice", "Rice", "1121", "Extra long grain", "100630", "Karnataka", "Jute",
             500, 20, 200, 25, "1050.00", "1150.00", "Chennai",
             "Steam-processed 1121, average grain length 8.3 mm, 2024 crop."),
        ],
    ),
    dict(
        email="joseph@malabarspice.demo", full_name="Joseph Mathew", phone="+91 98470 11002",
        company="Malabar Spice Traders LLP", entity_type="llp", industry="Spices processing and export",
        address="Willingdon Island, Warehouse Road", city="Kochi", state="Kerala", pincode="682003",
        intro="Spice processor and exporter of pepper and cardamom from Kerala's growing districts.",
        listings=[
            ("Black Pepper 550 GL", "Spices", "Malabar", "550 g/l", "090411", "Kerala", "Jute",
             60, 5, 25, 20, "5200.00", "5600.00", "Kochi",
             "Machine-cleaned, steam sterilised on request, moisture below 12%."),
            ("Green Cardamom 8 mm Bold", "Spices", "Alleppey Green", "8 mm bold", "090831", "Kerala", "Other",
             15, 1, 5, 15, "14000.00", "15500.00", "Kochi",
             "Hand-graded, deep green colour, packed in nitrogen-flushed bags."),
        ],
    ),
    dict(
        email="rajesh@deccanpulses.demo", full_name="Rajesh Jain", phone="+91 98260 11003",
        company="Deccan Pulses and Grains Pvt Ltd", entity_type="private_ltd", industry="Pulses processing",
        address="Sector E, Sanwer Road Industrial Area", city="Indore", state="Madhya Pradesh", pincode="452015",
        intro="Pulses processing unit supplying chickpeas and lentils to importers in the Middle East.",
        listings=[
            ("Kabuli Chana 42-44 Count", "Pulses", "Kabuli", "42-44 count", "071320", "Madhya Pradesh",
             "PP woven", 400, 25, 150, 21, "980.00", "1050.00", "Nhava Sheva",
             "Machine-cleaned, sortexed, 2024 crop."),
            ("Toor Dal (Arhar), Unpolished", "Pulses", "Arhar", "Premium", "071360", "Madhya Pradesh",
             "PP woven", 300, 20, 120, 18, "1150.00", "1250.00", "Nhava Sheva",
             "Unpolished, even-sized split pigeon peas."),
        ],
    ),
    dict(
        email="sunil@godavarisugar.demo", full_name="Sunil Patil", phone="+91 98230 11004",
        company="Godavari Sugar and Agro Ltd", entity_type="public_ltd", industry="Sugar and grain trading",
        address="Shirol Road, Jaysingpur", city="Kolhapur", state="Maharashtra", pincode="416101",
        intro="Integrated sugar mill also trading milling wheat from Maharashtra and Madhya Pradesh.",
        listings=[
            ("ICUMSA 45 White Refined Sugar", "Sugar", "S-30", "ICUMSA 45", "170199", "Maharashtra",
             "PP woven", 2000, 100, 1000, 30, "540.00", "580.00", "Nhava Sheva",
             "Refined white sugar, 50 kg bags, polarity 99.8% minimum."),
            ("Lokwan Milling Wheat", "Wheat", "Lokwan", "Milling grade", "100199", "Madhya Pradesh",
             "Bulk", 3000, 200, 1500, 30, "290.00", "320.00", "Mundra",
             "Hard golden grain, protein 11-12%, suitable for atta and flour."),
        ],
    ),
]

BUYERS: list[dict] = [
    dict(
        email="faisal@alnoorfoods.demo", full_name="Faisal Rahman", phone="+971 50 110 2001",
        company="Al Noor Foodstuff Trading LLC", entity_type="private_ltd", industry="Food import and distribution",
        address="Warehouse 7, Al Quoz Industrial Area 3", city="Dubai", state="Dubai", pincode=None, country="AE",
        intro="Importer of rice, pulses and spices for UAE supermarkets and food service.",
    ),
    dict(
        email="mariam@gulfharvest.demo", full_name="Mariam Al Suwaidi", phone="+971 50 110 2002",
        company="Gulf Harvest General Trading LLC", entity_type="private_ltd", industry="Commodity trading",
        address="Office 512, Al Taawun Tower", city="Sharjah", state="Sharjah", pincode=None, country="AE",
        intro="Trading house supplying sugar and wheat to GCC food manufacturers.",
    ),
    dict(
        email="omar@emiratesgrain.demo", full_name="Omar Haddad", phone="+971 50 110 2003",
        company="Emirates Grain Distributors LLC", entity_type="private_ltd", industry="Grain distribution",
        address="Plot 22, Mussafah Industrial Area", city="Abu Dhabi", state="Abu Dhabi", pincode=None, country="AE",
        intro="Distributor of grains and pulses across Abu Dhabi and Al Ain.",
    ),
    dict(
        email="priya@freshbasket.demo", full_name="Priya Nair", phone="+91 98200 11005",
        company="Fresh Basket Retail Pvt Ltd", entity_type="private_ltd", industry="Grocery retail",
        address="Unit 3, Kanjurmarg Industrial Estate", city="Mumbai", state="Maharashtra", pincode="400078",
        country="IN", intro="Grocery chain buying staples and spices for 40 stores in Maharashtra.",
    ),
]


async def _business(db, row: dict, *, role: str) -> tuple[User, bool]:
    """The verified business and its owner for ``row``; created if new."""
    now = utcnow()
    user = await masking.user_by_email(db, row["email"])
    created = user is None
    if created:
        business = Business(country=row.get("country", "IN"), verification_status=BusinessStatus.draft)
        user = User(business=business, role=UserRole.owner, password_hash=hash_password(PASSWORD),
                    account_status=AccountStatus.active, email_verified_at=now, consent_at=now,
                    consent_version="2026-08-29", position="Director")
        db.add_all([business, user])
        await db.flush()  # the vault rows need the ids
        masking.start_person(db, user.id, full_name=row["full_name"], email=row["email"])
        masking.start_identity(db, business.id, legal_name=row["company"])
    person = await masking.own_person(db, user.id)
    person.full_name, person.phone = row["full_name"], row["phone"]
    business = user.business
    identity = await masking.own_identity(db, business.id)
    identity.legal_name = row["company"]
    # One address field since 0036: street, city and postcode together.
    identity.address_line = ", ".join(x for x in (row["address"], row["city"], row["pincode"]) if x)
    business.country = row.get("country", "IN")
    business.state = row["state"]
    business.entity_type = row["entity_type"]
    business.industry = row["industry"]
    business.company_introduction = row["intro"]
    business.trade_position = role
    business.operating_countries = ["IN", "AE"]
    business.target_markets = ["AE"] if role == "seller" else None
    business.verification_status = BusinessStatus.verified
    business.verification_submitted_at = business.verification_submitted_at or now
    business.verified_at = business.verified_at or now
    business.verification_rejected_reason = None
    await masking.assign_code(db, business)
    await db.flush()
    credits = SELLER_CREDITS if role == "seller" else BUYER_CREDITS
    await post_credits(db, business.id, "ADJUSTMENT", credits, idempotency_key=f"seed-marketplace:{row['email']}",
                       note="Test credits for the test environment")
    return user, created


async def _listings(db, user: User, listings: list[tuple]) -> int:
    existing = set(await db.scalars(
        select(Product.name).where(Product.business_id == user.business_id, Product.deleted_at.is_(None))
    ))
    today, added = utcnow().date(), 0
    for (name, category, variety, grade, hs, origin, packaging, qty, moq, cap, lead,
         low, high, port, description) in listings:
        # Written on every run: the test environment keeps uploads in the
        # container, so a redeploy loses the photo files of listings it seeded.
        photo = await photo_for(category)
        if name in existing:
            continue
        db.add(Product(
            business_id=user.business_id, created_by_user_id=user.id, name=name, category=category,
            variety=variety, grade=grade, hs_code=hs, origin_country="IN", origin_state=origin,
            packaging=packaging, quantity=Decimal(qty), unit="MT", moq=Decimal(moq),
            capacity_per_month=Decimal(cap), capacity_unit="MT", lead_time_days=lead,
            price_per_unit=Decimal(low), price_max=Decimal(high), currency="USD",
            price_valid_until=today + timedelta(days=90), incoterms=["FOB", "CIF"], port_of_loading=port,
            description=description, photos=[photo],
            # Seeded listings skip the review queue, as seed_demo's do.
            status="published", submitted_at=utcnow(), published_at=utcnow(),
        ))
        added += 1
    return added


async def main() -> None:
    configure_integrations(settings)
    new_people = new_listings = 0
    async with SessionLocal() as db:
        for row in SELLERS:
            user, created = await _business(db, row, role="seller")
            new_people += created
            new_listings += await _listings(db, user, row["listings"])
        for row in BUYERS:
            _, created = await _business(db, row, role="buyer")
            new_people += created
        await db.commit()
        await recompute_price_usd(db)
        await db.commit()
        codes = dict((await db.execute(
            select(User.id, Business.company_code).join(Business, Business.id == User.business_id)
        )).all())
        print(f"Added {new_people} businesses and {new_listings} listings. Password for everyone: {PASSWORD}")
        for kind, rows in (("Seller", SELLERS), ("Buyer", BUYERS)):
            for row in rows:
                user = await masking.user_by_email(db, row["email"])
                print(f"  {kind:6}  {codes.get(user.id) or '-':10}  {row['email']:32}  {row['company']}")


if __name__ == "__main__":
    asyncio.run(main())
