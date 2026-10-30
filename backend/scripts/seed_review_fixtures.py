"""Seed three businesses waiting in the KYB review queue (local dev only).

Each signs up through the real API (in-process, so encryption, validation
and every rule apply), fills the business profile, adds GSTIN + PAN and
sends the profile for review:

    review1@review.cor1x.co … review3@review.cor1x.co

Requires DEBUG=true (the signup code is read from the dev response) and is
refused against Postgres unless --force is given. Accounts that already
exist are skipped. Passwords come from --password (default below) — local
test values only.

    python scripts/seed_review_fixtures.py
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402

FIXTURES = (
    ("review1@review.cor1x.co", "Asha Rao", "Kaveri Grain Traders Pvt Ltd", "12 Mill Road", "Karnal", "Haryana",
     "06AABCK1234M1Z2", "AABCK1234M"),
    ("review2@review.cor1x.co", "Vikram Nair", "Malabar Coast Spices LLP", "4 Mattancherry Road", "Kochi", "Kerala",
     "32AAFFM5678N1Z4", "AAFFM5678N"),
    ("review3@review.cor1x.co", "Farah Sheikh", "Deccan Pulses Exports Pvt Ltd", "88 Market Yard", "Latur",
     "Maharashtra", "27AACCD9012P1Z6", "AACCD9012P"),
)


async def seed_one(c: httpx.AsyncClient, fx: tuple, password: str) -> str:
    email, name, company, address, city, state, gstin, pan = fx
    r = await c.post("/auth/signup/code", json={"email": email})
    if r.status_code == 409:
        return f"skip   {email} (already exists)"
    r.raise_for_status()
    code = r.json().get("devCode")
    if not code:
        raise SystemExit("No dev code in the response — run with DEBUG=true.")
    (await c.post("/auth/signup/verify", json={"email": email, "code": code})).raise_for_status()
    r = await c.post(
        "/auth/signup/complete",
        json={"email": email, "fullName": name, "companyName": company, "password": password, "acceptTerms": True},
    )
    r.raise_for_status()
    r = await c.put(
        "/me/business-profile",
        json={"legalName": company, "country": "IN", "addressLine": address, "city": city, "state": state},
    )
    r.raise_for_status()
    types = {t["code"]: t["id"] for t in (await c.get("/kyb/document-types")).json()}
    for code_, value in (("gstin", gstin), ("pan", pan)):
        (await c.post("/me/verification-docs", data={"documentTypeId": types[code_], "value": value})).raise_for_status()
    (await c.post("/me/submit-verification")).raise_for_status()
    return f"seeded {email} — {company}, sent for review"


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--password", default="Review-Test-2026", help="password for the test accounts")
    ap.add_argument("--force", action="store_true", help="allow a non-SQLite database")
    args = ap.parse_args()
    if not settings.debug:
        raise SystemExit("Refusing: DEBUG is false (this is for local development).")
    if not settings.is_sqlite and not args.force:
        raise SystemExit("Refusing: DATABASE_URL is not SQLite. Pass --force if you really mean it.")
    for fx in FIXTURES:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as c:
            print(await seed_one(c, fx, args.password))


if __name__ == "__main__":
    asyncio.run(main())
