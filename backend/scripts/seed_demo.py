"""Seed a handful of verified sellers + products for the public catalog.

Idempotent — matches sellers by email and products by name. Not called on
startup. Run (from anywhere)::

    backend/.venv/bin/python backend/scripts/seed_demo.py

Every seller (one business + its owner) gets all seven mandatory
verification fields and business status ``verified``. Every product gets a
photo stored via the storage integration (so it is served by GET /uploads/products/<32hex>.<ext>):

* Rice, Sugar, Wheat, Pulses, Spices — the commodity photograph from
  ``frontend/public/media/gen/<category>-1280.webp`` (the same images the
  frontend uses through ``lib/media.ts``). Content-addressed filename, so a
  regenerated photo gets a fresh URL past the immutable cache.
* anything else (or when the frontend folder is absent, e.g. a backend-only
  deploy) — a generated sand-toned placeholder PNG.

Re-running also upgrades existing demo products that still carry the old
placeholder to the photograph.
"""
from __future__ import annotations

import asyncio
import hashlib
import random
import struct
import sys
import zlib
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.core.time import utcnow  # noqa: E402
from app.modules.fx.service import recompute_price_usd  # noqa: E402
from app.main import configure_integrations  # noqa: E402
from app.integrations.storage import IMAGE_TYPES, detect, get_storage  # noqa: E402
from app.models.business import Business, BusinessStatus  # noqa: E402
from app.models.product import Product  # noqa: E402
from app.models.user import AccountStatus, User, UserRole  # noqa: E402

PASSWORD = "DemoPass123!"

# (email, full_name, phone, city, state, company, [(name, category, variety,
#   origin_state, packaging, quantity, moq, price, description)])
_SEED: list[tuple] = [
    ("ramesh@kaverifoods.demo", "Ramesh Kumar", "+91 9000000001", "Karnal", "Haryana", "Kaveri Foods Pvt Ltd", [
        ("1121 Steam Basmati", "Rice", "1121", "Haryana", "Jute", 500, 25, "72.00", "Aromatic long-grain, 2024 crop."),
        ("Pusa Sella Rice", "Rice", "Pusa", "Haryana", "PP woven", 300, 50, "64.00", "Parboiled Pusa, mill-fresh."),
    ]),
    ("vishnu@vishnurice.demo", "Vishnu Agrawal", "+91 9000000002", "Amritsar", "Punjab", "Vishnu Rice Mills", [
        ("Sharbati Basmati", "Rice", "Sharbati", "Punjab", "Jute", 200, 25, "58.50", "Medium-grain aromatic."),
        ("Sona Masoori", "Rice", "Sona Masoori", "Andhra Pradesh", "PP woven", 800, 100, "42.00", "Short-grain non-basmati."),
    ]),
    ("priya@nairspice.demo", "Priya Nair", "+91 9000000003", "Kochi", "Kerala", "Nair Spice & Grain", [
        ("Matta Rice", "Rice", "Rosematta", "Kerala", "PP woven", 400, 50, "48.00", "Kerala red rice, parboiled."),
        ("Black Pepper", "Spices", "Malabar", "Kerala", "Jute", 50, 5, "520.00", "Bold Malabar pepper."),
    ]),
    ("karthik@reddyagro.demo", "Karthik Reddy", "+91 9000000004", "Vijayawada", "Andhra Pradesh", "Reddy Agro Exports", [
        ("HMT Rice", "Rice", "HMT", "Andhra Pradesh", "PP woven", 1200, 100, "38.00", "Everyday HMT, sortex clean."),
    ]),
    ("sanjay@patelgrains.demo", "Sanjay Patel", "+91 9000000006", "Ahmedabad", "Gujarat", "Patel Grains", [
        ("Tur Dal", "Pulses", "Tur", "Gujarat", "PP woven", 500, 50, "110.00", "Deshelled tur, clean."),
        ("Sugar (M-30)", "Sugar", "M-30", "Gujarat", "PP woven", 5000, 500, "38.00", "Refined mill sugar."),
    ]),
]


def _placeholder_png(seed: bytes, size: int = 160) -> bytes:
    """A warm, grainy sand-toned PNG — the "drawn grain" stand-in for
    product photography — generated without image libraries."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    rnd = random.Random(seed)
    tones = [(239, 230, 210), (226, 214, 186), (217, 204, 176), (232, 222, 196)]
    a = tones[seed[0] % len(tones)]
    b = (a[0] - 34, a[1] - 38, a[2] - 46)
    rows = bytearray()
    for y in range(size):
        rows.append(0)  # PNG filter: none
        for x in range(size):
            t = (x + y) / (2 * (size - 1))
            n = rnd.randint(-9, 9)
            rows.extend(max(0, min(255, int(a[i] + (b[i] - a[i]) * t) + n)) for i in range(3))
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(rows))) + chunk(b"IEND", b"")


# Commodity photography shipped with the frontend (see frontend/lib/media.ts).
MEDIA_DIR = Path(__file__).resolve().parents[2] / "frontend" / "public" / "media" / "gen"
COMMODITY_PHOTOS: dict[str, str] = {
    "Rice": "rice-1280.webp",
    "Sugar": "sugar-1280.webp",
    "Wheat": "wheat-1280.webp",
    "Pulses": "pulses-1280.webp",
    "Spices": "spices-1280.webp",
}

_photo_cache: dict[str, str] = {}


def placeholder_url(category: str) -> str:
    """URL of the generated placeholder for ``category`` (old seeds used it)."""
    digest = hashlib.md5(f"demo-{category}".encode()).hexdigest()
    return f"/uploads/products/{digest}.png"


async def _store_commodity_photo(category: str) -> str | None:
    """Store the category's photograph; None if there is no usable file."""
    name = COMMODITY_PHOTOS.get(category)
    path = MEDIA_DIR / name if name else None
    if path is None or not path.is_file():
        return None
    data = path.read_bytes()
    ftype = detect(data)
    if ftype is None or ftype not in IMAGE_TYPES:
        return None
    # 32 hex chars, as the catalog requires — content-addressed.
    key = f"products/{hashlib.md5(data).hexdigest()}.{ftype.ext}"
    storage = get_storage()
    if not await storage.exists(key):
        await storage.save(data, key, ftype.mime)
    return f"/uploads/{key}"


async def photo_for(category: str) -> str:
    """Public photo URL for a demo product of ``category``."""
    if category in _photo_cache:
        return _photo_cache[category]
    url = await _store_commodity_photo(category)
    if url is None:
        digest = hashlib.md5(f"demo-{category}".encode()).hexdigest()
        key = f"products/{digest}.png"
        # Always rewrite so re-running the seed refreshes the placeholder art.
        await get_storage().save(_placeholder_png(bytes.fromhex(digest)), key, "image/png")
        url = f"/uploads/{key}"
    _photo_cache[category] = url
    return url


async def upgrade_placeholder_photo(product: Product) -> bool:
    """Swap a demo product's generated placeholder for its photograph.

    Only touches products whose photos are exactly the old placeholder, so
    anything a seller uploaded is left alone. Returns True if it changed.
    """
    if list(product.photos or []) != [placeholder_url(product.category)]:
        return False
    url = await photo_for(product.category)
    if url == placeholder_url(product.category):
        return False
    product.photos = [url]
    return True


async def _seller(db, row) -> User:
    email, full_name, phone, city, state, company, _ = row
    now = utcnow()
    user = await db.scalar(select(User).where(User.email == email))
    if user is None:
        business = Business(country="IN")
        user = User(business=business, email=email, role=UserRole.owner)
        db.add_all([business, user])
    user.password_hash = hash_password(PASSWORD)
    user.account_status = AccountStatus.active
    user.email_verified_at = user.email_verified_at or now
    user.full_name, user.position, user.phone = full_name, "Director", phone
    user.consent_at = user.consent_at or now
    user.consent_version = user.consent_version or "2026-08-29"
    user.deleted_at = None

    biz = user.business
    biz.legal_name = company
    biz.entity_type = "private_ltd" if "Pvt Ltd" in company else "proprietorship"
    biz.industry = "Agri commodities"
    biz.operating_countries = ["IN"]
    biz.trade_position = "seller"
    biz.city, biz.state, biz.country = city, state, "IN"
    biz.deleted_at = None
    biz.verification_status = BusinessStatus.verified
    biz.verification_submitted_at = biz.verification_submitted_at or now
    biz.verified_at = biz.verified_at or now
    biz.verification_rejected_reason = None
    await db.flush()
    return user


async def main() -> None:
    configure_integrations(settings)
    added = upgraded = 0
    async with SessionLocal() as db:
        for row in _SEED:
            user = await _seller(db, row)
            products = list(
                await db.scalars(
                    select(Product).where(Product.business_id == user.business_id, Product.deleted_at.is_(None))
                )
            )
            for product in products:
                upgraded += await upgrade_placeholder_photo(product)
            existing = {p.name for p in products}
            for name, category, variety, origin, packaging, qty, moq, price, desc in row[6]:
                if name in existing:
                    continue
                db.add(
                    Product(
                        business_id=user.business_id,
                        created_by_user_id=user.id,
                        name=name,
                        category=category,
                        variety=variety,
                        origin_state=origin,
                        packaging=packaging,
                        quantity=Decimal(qty),
                        unit="MT",
                        moq=Decimal(moq),
                        price_per_unit=Decimal(price),
                        description=desc,
                        photos=[await photo_for(category)],
                    )
                )
                added += 1
        await db.commit()
        # Fill price_usd from the stored rates (no network).
        await recompute_price_usd(db)
    print(
        f"Seeded {len(_SEED)} verified sellers (password {PASSWORD}); added {added} products; "
        f"upgraded {upgraded} placeholder photos."
    )


if __name__ == "__main__":
    asyncio.run(main())
