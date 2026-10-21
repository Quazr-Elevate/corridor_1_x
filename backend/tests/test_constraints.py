"""Every UNIQUE / CHECK from docs/04_data_model.md rejects bad rows at the
database level, and services turn the reachable ones into friendly errors."""
from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from conftest import signup_and_login
from sqlalchemy import insert, update
from sqlalchemy.exc import IntegrityError

from app.core.db import SessionLocal
from app.core.errors import BadRequest
from app.core.time import utcnow
from app.models import (
    Business,
    BusinessDocument,
    ContactReveal,
    EmailCode,
    Product,
    User,
)

NOW = utcnow()


async def _insert(table, **values):
    async with SessionLocal() as db:
        await db.execute(insert(table), [values])
        await db.commit()


async def _business(**over) -> uuid.UUID:
    bid = uuid.uuid4()
    await _insert(Business.__table__, **({"id": bid, "country": "IN", "verification_status": "draft"} | over))
    return bid


async def _user(business_id: uuid.UUID, **over) -> uuid.UUID:
    uid = uuid.uuid4()
    values = dict(
        id=uid,
        business_id=business_id,
        role="owner",
        email=f"u-{uid.hex[:8]}@acme.in",
        password_hash="x",
        account_status="active",
        email_verified_at=NOW,
        full_name="Test User",
        session_version=0,
    )
    values.update(over)
    await _insert(User.__table__, **values)
    return uid


async def _product(business_id: uuid.UUID, **over) -> uuid.UUID:
    pid = uuid.uuid4()
    values = dict(id=pid, business_id=business_id, name="Basmati", category="Rice", unit="MT", currency="INR", photos=[])
    values.update(over)
    await _insert(Product.__table__, **values)
    return pid


async def _rejects(coro_factory) -> IntegrityError:
    with pytest.raises(IntegrityError) as exc:
        await coro_factory()
    return exc.value


# ── businesses ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "values, name",
    [
        ({"trade_position": "trader"}, "ck_businesses_trade_position"),
        ({"entity_type": "corporation"}, "ck_businesses_entity_type"),
        ({"country": "IND"}, "ck_businesses_country"),
        ({"verification_status": "verified", "verification_submitted_at": NOW}, "ck_businesses_verified_has_date"),
        ({"verification_status": "rejected", "verification_submitted_at": NOW}, "ck_businesses_rejected_has_reason"),
        ({"verification_status": "pending_verification"}, "ck_businesses_submitted_has_date"),
    ],
)
async def test_business_checks(values, name):
    base = {"id": uuid.uuid4(), "country": "IN", "verification_status": "draft"}
    base.update(values)
    err = await _rejects(lambda: _insert(Business.__table__, **base))
    assert name in str(err.orig)


async def test_business_consistent_states_are_accepted():
    await _business(verification_status="verified", verification_submitted_at=NOW, verified_at=NOW)
    await _business(verification_status="rejected", verification_submitted_at=NOW, verification_rejected_reason="x")
    await _business(verification_status="pending_verification", verification_submitted_at=NOW)
    await _business(trade_position="both", entity_type="llp")


@pytest.mark.parametrize("column", ["legal_name_normalized", "website_normalized"])
async def test_business_unique_only_among_live_rows(column):
    await _business(**{column: "acme"})
    err = await _rejects(lambda: _business(**{column: "acme"}))
    assert column in str(err.orig)
    # A deleted business doesn't block re-registration.
    await _business(**{column: "gone", "deleted_at": NOW})
    await _business(**{column: "gone"})


# ── users ────────────────────────────────────────────────────────────


async def test_user_checks_and_uniques():
    bid = await _business()
    await _user(bid, email="owner@acme.in", phone_normalized="+911")

    err = await _rejects(lambda: _user(bid, role="member", email="Mixed@Acme.in"))
    assert "ck_users_email_lowercase" in str(err.orig)
    err = await _rejects(lambda: _user(bid, role="member", session_version=-1))
    assert "ck_users_session_version" in str(err.orig)
    await _rejects(lambda: _user(bid, role="member", email="owner@acme.in"))  # uq_users_email
    err = await _rejects(lambda: _user(bid, role="member", phone_normalized="+911"))
    assert "phone_normalized" in str(err.orig)
    # One owner per business; members are fine; a deleted owner doesn't count.
    await _rejects(lambda: _user(bid, role="owner"))
    await _user(bid, role="member")
    other = await _business()
    await _user(other, role="owner", deleted_at=NOW, phone_normalized="+922")
    await _user(other, role="owner", phone_normalized="+922")  # deleted user's phone is free


# ── email_codes ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "values, name",
    [
        ({"attempts": 6}, "ck_email_codes_attempts"),
        ({"attempts": -1}, "ck_email_codes_attempts"),
        ({"consumed_at": NOW}, "ck_email_codes_order"),
    ],
)
async def test_email_code_checks(values, name):
    row = dict(
        id=uuid.uuid4(),
        email="a@acme.in",
        purpose="signup",
        code_hash="0" * 64,
        attempts=0,
        expires_at=NOW + timedelta(minutes=10),
    )
    row.update(values)
    err = await _rejects(lambda: _insert(EmailCode.__table__, **row))
    assert name in str(err.orig)


# ── business_documents ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "values, name",
    [
        ({"size_bytes": 0}, "ck_business_documents_size"),
        ({"size_bytes": 10 * 1024 * 1024 + 1}, "ck_business_documents_size"),
        ({"status": "rejected"}, "ck_business_documents_rejected_reason"),
    ],
)
async def test_document_checks(values, name):
    bid = await _business()
    row = dict(
        id=uuid.uuid4(),
        business_id=bid,
        doc_type="GST",
        original_filename="g.pdf",
        storage_key="verification/x/g.pdf",
        mime_type="application/pdf",
        size_bytes=10,
        status="pending",
    )
    row.update(values)
    err = await _rejects(lambda: _insert(BusinessDocument.__table__, **row))
    assert name in str(err.orig)


# ── products ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "values, name",
    [
        ({"category": "Gold"}, "ck_products_category"),
        ({"unit": "tons"}, "ck_products_unit"),
        ({"currency": "RUPEE"}, "ck_products_currency"),
        ({"quantity": Decimal("-1")}, "ck_products_amounts"),
        ({"moq": Decimal("-1")}, "ck_products_amounts"),
        ({"price_per_unit": Decimal("-0.01")}, "ck_products_amounts"),
        ({"quantity": Decimal("10"), "moq": Decimal("11")}, "ck_products_moq_le_quantity"),
        ({"name": " a "}, "ck_products_name_length"),
    ],
)
async def test_product_checks(values, name):
    bid = await _business()
    err = await _rejects(lambda: _product(bid, **values))
    assert name in str(err.orig)


# ── contact_reveals ──────────────────────────────────────────────────


async def test_reveal_unique_and_not_self():
    buyer, seller = await _business(), await _business()
    pid = await _product(seller)
    await _insert(ContactReveal.__table__, id=uuid.uuid4(), buyer_business_id=buyer, seller_business_id=seller, product_id=pid)
    err = await _rejects(
        lambda: _insert(
            ContactReveal.__table__, id=uuid.uuid4(), buyer_business_id=buyer, seller_business_id=seller, product_id=pid
        )
    )
    assert "buyer_business_id" in str(err.orig) or "uq_contact_reveals_buyer_product" in str(err.orig)
    err = await _rejects(
        lambda: _insert(
            ContactReveal.__table__, id=uuid.uuid4(), buyer_business_id=seller, seller_business_id=seller, product_id=pid
        )
    )
    assert "ck_contact_reveals_not_self" in str(err.orig)


# ── services map violations to friendly errors ───────────────────────


async def test_unique_index_race_on_company_name_maps_to_409(client, make_client, monkeypatch):
    import app.modules.accounts.service as accounts

    await signup_and_login(client, "n1@kaverifoods.in")
    body = {"legalName": "Kaveri Foods", "industry": "Rice", "operatingCountries": ["IN"]}
    assert (await client.post("/onboarding/company", json=body)).status_code == 200

    async def no_check(*_a, **_k):
        return None

    monkeypatch.setattr(accounts, "ensure_company_available", no_check)
    other = make_client()
    await signup_and_login(other, "n2@othermill.in")
    r = await other.post("/onboarding/company", json=body)
    assert r.status_code == 409
    assert r.json()["detail"] == "This legal company name is already registered on Cor1x."


async def test_check_violation_maps_to_400():
    """A request that slipped past the schema (model_construct) still gets a
    friendly 400 from the CHECK constraint, not a 500."""
    from app.modules.catalog import service as catalog
    from app.modules.catalog.schemas import ProductCreate

    bid = await _business()
    uid = await _user(bid)

    async def no_photo_check(photos):
        return photos

    payload = ProductCreate.model_construct(
        name="Basmati",
        category="Rice",
        variety=None,
        origin_state=None,
        packaging=None,
        quantity=Decimal("5"),
        unit="MT",
        moq=Decimal("50"),
        price_per_unit=None,
        currency="INR",
        description=None,
        photos=["/uploads/products/x.png"],
    )
    orig = catalog._validate_photos
    catalog._validate_photos = no_photo_check
    try:
        async with SessionLocal() as db:
            user = await db.get(User, uid)
            with pytest.raises(BadRequest) as exc:
                await catalog.create_product(db, user, payload)
    finally:
        catalog._validate_photos = orig
    assert exc.value.detail == "MOQ can't be larger than the available quantity."


async def test_status_check_blocks_inconsistent_service_writes():
    """Even a buggy write path can't store a verified business without a date."""
    bid = await _business()
    async with SessionLocal() as db:
        with pytest.raises(IntegrityError):
            await db.execute(
                update(Business)
                .where(Business.id == bid)
                .values(verification_status="verified", verification_submitted_at=NOW)
            )
            await db.commit()


# ── Foreign keys (SQLite only enforces them with PRAGMA foreign_keys=ON) ──


async def test_foreign_keys_enforced_on_insert():
    # a product pointing at a business that doesn't exist must be refused
    await _rejects(lambda: _product(uuid.uuid4()))


async def test_delete_business_cascades_and_restricts():
    from sqlalchemy import delete, func, select

    bid = await _business()
    await _product(bid)
    # users → businesses is RESTRICT: can't delete a business that still has users
    uid = await _user(bid)
    async def _delete_business():
        async with SessionLocal() as db:
            await db.execute(delete(Business).where(Business.id == bid))
            await db.commit()
    await _rejects(_delete_business)

    # once its users are gone, deleting the business cascades to its products
    async with SessionLocal() as db:
        await db.execute(delete(User).where(User.id == uid))
        await db.commit()
    await _delete_business()
    async with SessionLocal() as db:
        left = await db.scalar(select(func.count()).select_from(Product).where(Product.business_id == bid))
    assert left == 0
