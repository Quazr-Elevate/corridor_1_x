"""QA-100 — Signup country field (FLOW-100).

Validates that the new mandatory ``country`` field on
``POST /auth/signup/complete`` is enforced, normalized, and persisted to
``business.country`` + ``business.operating_countries``.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.business import Business
from app.models.user import User
from tests.conftest import SessionLocal, code_from_email
from tests.qa.conftest import uniq


async def _codes_and_verify(c, email: str) -> None:
    r = await c.post("/auth/signup/code", json={"email": email})
    assert r.status_code == 200, r.text
    r = await c.post("/auth/signup/verify", json={"email": email, "code": code_from_email(email)})
    assert r.status_code == 200, r.text


# QA-100.1
async def test_signup_country_missing_rejected(client):
    email = f"{uniq('qa100')}@test.cor1x.co"
    await _codes_and_verify(client, email)
    r = await client.post(
        "/auth/signup/complete",
        json={"email": email, "fullName": "Alice Smith", "password": "Sup3r-secret!", "acceptTerms": True},
    )
    assert r.status_code == 422
    body = r.json()["detail"]
    # Pydantic lists the missing field explicitly.
    assert any(e.get("loc") == ["body", "country"] and e.get("type") == "missing" for e in body), body


# QA-100.2
async def test_signup_country_invalid_rejected(client):
    email = f"{uniq('qa100')}@test.cor1x.co"
    await _codes_and_verify(client, email)
    r = await client.post(
        "/auth/signup/complete",
        json={
            "email": email,
            "fullName": "Alice Smith",
            "password": "Sup3r-secret!",
            "acceptTerms": True,
            "country": "XX",
        },
    )
    assert r.status_code == 422
    assert "Unknown country code" in r.text


# QA-100.3
async def test_signup_country_lowercase_normalized(client):
    email = f"{uniq('qa100')}@test.cor1x.co"
    await _codes_and_verify(client, email)
    r = await client.post(
        "/auth/signup/complete",
        json={
            "email": email,
            "fullName": "Alice Smith",
            "password": "Sup3r-secret!",
            "acceptTerms": True,
            "country": "in",
        },
    )
    assert r.status_code == 201, r.text
    # DB side: country stored as alpha-2 uppercase; operating_countries seeded.
    async with SessionLocal() as db:
        row = (await db.execute(select(User).where(User.email == email))).scalar_one()
        biz = (await db.execute(select(Business).where(Business.id == row.business_id))).scalar_one()
        assert biz.country == "IN"
        assert biz.operating_countries == ["IN"]


# QA-100.4
async def test_signup_country_alpha3_normalized(client):
    email = f"{uniq('qa100')}@test.cor1x.co"
    await _codes_and_verify(client, email)
    r = await client.post(
        "/auth/signup/complete",
        json={
            "email": email,
            "fullName": "Alice Smith",
            "password": "Sup3r-secret!",
            "acceptTerms": True,
            "country": "IND",
        },
    )
    assert r.status_code == 201, r.text
    async with SessionLocal() as db:
        row = (await db.execute(select(User).where(User.email == email))).scalar_one()
        biz = (await db.execute(select(Business).where(Business.id == row.business_id))).scalar_one()
        assert biz.country == "IN"
