from __future__ import annotations

import re
import uuid
from datetime import timedelta

import pytest

from conftest import complete_listing, fill_mandatory, publish_listing, set_status, signup_and_login, upload_photo
from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.time import utcnow
from app.models.contact_reveal import ContactReveal
from app.models.product import Product
from app.models.user import User

from app.models.business import BusinessStatus


_photo = upload_photo


def _product(photos, **over):
    body = {
        "name": "1121 Steam Basmati",
        "category": "Rice",
        "quantity": "500",
        "moq": "25",
        "priceMin": "72.50",
        "priceMax": "80.00",
        "description": "Aromatic long grain",
        "photos": photos,
    }
    body.update(over)
    return body


async def test_photo_upload_and_serving(client, make_client):
    await signup_and_login(client, "ph@kaverifoods.in")
    r = await client.post(
        "/products/upload-photo", files={"file": ("x.png", b"<html>evil</html>", "image/png")}
    )
    assert r.status_code == 415
    url = await _photo(client)
    assert url.startswith("/uploads/products/") and url.endswith(".png")
    r = await make_client().get(url)  # public
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["content-disposition"] == "inline"
    assert (await client.get("/uploads/products/../../cor1x.db")).status_code == 404
    assert (await client.get("/uploads/products/nothere.png")).status_code == 404


async def test_product_validation(client):
    await signup_and_login(client, "pv@kaverifoods.in")
    url = await _photo(client)
    assert (await client.post("/products", json=_product([url], name="X"))).status_code == 422
    assert (await client.post("/products", json=_product([url], priceMin="-1"))).status_code == 422
    assert (await client.post("/products", json=_product([url], priceMax="70"))).status_code == 422  # max < min
    assert (await client.post("/products", json=_product([url], description="d" * 5001))).status_code == 422
    assert (await client.post("/products", json=_product([url], category="Gold"))).status_code == 422
    assert (await client.post("/products", json=_product([url], moq="600"))).status_code == 422  # moq > quantity
    assert (await client.post("/products", json=_product([url], currency="RUPEES"))).status_code == 422
    assert (await client.post("/products", json=_product([url], hsCode="10-06"))).status_code == 422
    assert (await client.post("/products", json=_product([url], incoterms=["FOB", "XYZ"]))).status_code == 422
    assert (await client.post("/products", json=_product([url], leadTimeDays=-1))).status_code == 422
    # The client never sets the review status.
    r = await client.post("/products", json=_product([url], status="published"))
    assert r.status_code == 422 and r.json()["code"] == "request.unknown_field"
    r = await client.post("/products", json=_product(["https://evil.example/x.png"]))
    assert r.status_code == 400
    r = await client.post("/products", json=_product(["/uploads/products/" + "a" * 32 + ".png"]))
    assert r.status_code == 400  # well-formed but never uploaded
    many = [await _photo(client) for _ in range(6)]
    r = await client.post("/products", json=_product(many))
    assert r.status_code == 400 and "At most 5" in r.json()["detail"]
    # A maximum price needs a minimum.
    r = await client.post("/products", json={"name": "No floor", "category": "Rice", "priceMax": "10"})
    assert r.status_code == 400 and "minimum price" in r.json()["detail"]

    r = await client.post("/products", json=_product([url, url]))
    assert r.status_code == 201, r.text
    assert r.json()["photos"] == [url] and r.json()["status"] == "draft"
    listed = (await client.get("/products")).json()
    assert listed["total"] == 1
    first = listed["items"][0]
    assert (first["priceMin"], first["priceMax"], first["currency"]) == ("72.50", "80.00", "INR")

    # Soft delete: gone from the business's list; only the owner business can delete.
    pid = first["id"]
    assert (await client.delete(f"/products/{pid}")).status_code == 204
    assert (await client.get("/products")).json() == {"total": 0, "items": []}
    assert (await client.delete(f"/products/{pid}")).status_code == 404


async def test_market_visibility_needs_a_verified_business_and_a_published_listing(client, make_client, admin_client):
    seller = await signup_and_login(client, "seller@kaverifoods.in")
    await fill_mandatory(client, n=1)
    listing = await complete_listing(client)
    pid, url = listing["id"], listing["photos"][0]

    anon = make_client()
    # Draft business → not in the market, and it can't submit a listing yet.
    assert (await anon.get("/public/products")).json()["total"] == 0
    assert (await anon.get(f"/public/products/{pid}")).status_code == 404
    assert (await client.post(f"/products/{pid}/submit")).status_code == 403

    await client.post("/me/submit-verification")
    assert (await admin_client.post(f"/admin/users/{seller['userId']}/verify")).status_code == 200
    # A verified business is not enough: the listing itself must be approved.
    assert (await anon.get("/public/products")).json()["total"] == 0
    await publish_listing(client, admin_client, pid)

    listing = (await anon.get("/public/products?q=basmati")).json()
    assert listing["total"] == 1
    card = listing["items"][0]
    # the seller stays masked in public: no company name, no contact details
    assert "businessName" not in card["seller"]
    assert "Acme Agro" not in str(listing)
    assert set(card["seller"]) == {"companyCode", "state", "verified"}
    assert seller["businessId"] not in str(listing)
    assert "email" not in card["seller"]
    detail = (await anon.get(f"/public/products/{pid}")).json()
    assert detail["photos"] == [url]
    facets = (await anon.get("/public/catalog/facets")).json()
    assert facets["categories"] == [{"value": "Rice", "count": 1}]

    # Revoking the business hides its listings again.
    r = await admin_client.post(f"/admin/users/{seller['userId']}/reject", json={"reason": "Expired GST", "failedItems": ["legalName"]})
    assert r.status_code == 200
    assert (await anon.get("/public/products")).json()["total"] == 0
    assert (await admin_client.post(f"/admin/users/{seller['userId']}/verify")).status_code == 200
    assert (await anon.get("/public/products")).json()["total"] == 1

    # A deleted listing leaves the market.
    assert (await client.delete(f"/products/{pid}")).status_code == 204
    assert (await anon.get("/public/products")).json()["total"] == 0
    assert (await anon.get(f"/public/products/{pid}")).status_code == 404


async def _verified_seller_with_product(client, admin_client, email="seller@kaverifoods.in", n=1) -> tuple[dict, str]:
    seller = await signup_and_login(client, email)
    await fill_mandatory(client, n=n)
    pid = (await complete_listing(client))["id"]
    await client.post("/me/submit-verification")
    assert (await admin_client.post(f"/admin/users/{seller['userId']}/verify")).status_code == 200
    await publish_listing(client, admin_client, pid)
    return seller, pid


@pytest.fixture
def reveal_on(monkeypatch):
    """Contact reveal is off by default (A-030); these tests cover the code
    that remains until it is removed."""
    monkeypatch.setattr(settings, "contact_reveal_enabled", True)


async def test_contact_reveal_is_off_by_default(client, make_client, admin_client):
    seller, pid = await _verified_seller_with_product(client, admin_client)
    buyer = make_client()
    b = await signup_and_login(buyer, "buyer@othermill.in")
    await set_status(b["userId"], BusinessStatus.verified)
    r = await buyer.post(f"/products/{pid}/contact-reveal")
    assert r.status_code == 404 and r.json()["code"] == "resource.not_found"
    assert "Kaveri" not in r.text and "seller@kaverifoods.in" not in r.text
    async with SessionLocal() as db:
        assert list(await db.scalars(select(ContactReveal))) == []
    assert (await buyer.get("/me")).json()["contactRevealEnabled"] is False


async def test_contact_reveal_gates_and_idempotency(client, make_client, admin_client, reveal_on):
    seller, pid = await _verified_seller_with_product(client, admin_client)
    # Owner contact + business address in the reveal.
    r = await admin_client.patch(
        f"/admin/users/{seller['userId']}",
        json={"businessProfile": {"city": "Karnal", "state": "Haryana", "entityType": "private_ltd"}},
    )
    assert r.status_code == 200

    # The market shows the state and never the city (CX-068): card and detail.
    guest = make_client()
    card = (await guest.get("/public/products")).json()["items"][0]
    detail = (await guest.get(f"/public/products/{pid}")).json()
    for seller_view in (card["seller"], detail["seller"]):
        assert set(seller_view) == {"companyCode", "state", "verified"}
        assert seller_view["state"] == "Haryana"
        assert re.fullmatch(r"IN-\d{6}", seller_view["companyCode"])
    assert seller["businessId"] not in str(card) + str(detail)
    assert "Karnal" not in str(card) + str(detail)

    assert (await make_client().post(f"/products/{pid}/contact-reveal")).status_code == 401
    buyer = make_client()
    b = await signup_and_login(buyer, "buyer@othermill.in")
    # Buyer business not verified → 403.
    r = await buyer.post(f"/products/{pid}/contact-reveal")
    assert r.status_code == 403
    await set_status(b["userId"], BusinessStatus.verified)
    r = await buyer.post(f"/products/{pid}/contact-reveal")
    assert r.status_code == 200, r.text
    contact = r.json()
    assert contact["email"] == "seller@kaverifoods.in" and contact["fullName"] == "Asha Rao"
    assert contact["sellerId"] == seller["businessId"]
    assert (contact["city"], contact["entityType"], contact["country"]) == ("Karnal", "private_ltd", "IN")
    assert "businessType" not in contact
    again = await buyer.post(f"/products/{pid}/contact-reveal")
    assert again.json()["revealedAt"] == contact["revealedAt"]
    # Own business's listing → 400 (no self-reveal).
    assert (await client.post(f"/products/{pid}/contact-reveal")).status_code == 400
    assert (await buyer.post("/products/not-a-uuid/contact-reveal")).status_code == 404

    async with SessionLocal() as db:
        rows = list(await db.scalars(select(ContactReveal)))
    assert len(rows) == 1
    assert str(rows[0].buyer_business_id) == b["businessId"]
    assert str(rows[0].seller_business_id) == seller["businessId"]
    assert str(rows[0].revealed_by_user_id) == b["userId"]

    # Seller business unverified → product invisible → 404 for the reveal.
    await set_status(seller["userId"], BusinessStatus.rejected)
    assert (await buyer.post(f"/products/{pid}/contact-reveal")).status_code == 404


async def test_reveal_limit_is_per_business(client, make_client, admin_client, reveal_on):
    seller, pid = await _verified_seller_with_product(client, admin_client)
    buyer = make_client()
    b = await signup_and_login(buyer, "buyer@othermill.in")
    await set_status(b["userId"], BusinessStatus.verified)

    # 20 earlier reveals by this buyer business within the hour (other products).
    async with SessionLocal() as db:
        seller_user = await db.get(User, uuid.UUID(seller["userId"]))
        for i in range(20):
            p = Product(
                business_id=seller_user.business_id,
                name=f"Lot {i}",
                category="Rice",
                unit="MT",
                status="published",
                photos=["/uploads/products/" + "a" * 32 + ".png"],
            )
            db.add(p)
            await db.flush()
            db.add(
                ContactReveal(
                    buyer_business_id=uuid.UUID(b["businessId"]),
                    seller_business_id=seller_user.business_id,
                    product_id=p.id,
                    revealed_at=utcnow() - timedelta(minutes=5),
                )
            )
        await db.commit()
    r = await buyer.post(f"/products/{pid}/contact-reveal")
    assert r.status_code == 429 and "reveal limit" in r.json()["detail"]

    # Another verified business has its own budget.
    other = make_client()
    o = await signup_and_login(other, "other@thirdmill.in")
    await set_status(o["userId"], BusinessStatus.verified)
    assert (await other.post(f"/products/{pid}/contact-reveal")).status_code == 200
