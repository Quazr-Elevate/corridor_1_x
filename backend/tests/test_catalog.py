from __future__ import annotations

import uuid
from datetime import timedelta

from conftest import fill_mandatory, png_bytes, set_status, signup_and_login
from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.time import utcnow
from app.models.contact_reveal import ContactReveal
from app.models.product import Product
from app.models.user import User

from app.models.business import BusinessStatus


async def _photo(c) -> str:
    r = await c.post("/products/upload-photo", files={"file": ("p.png", png_bytes(), "image/png")})
    assert r.status_code == 201, r.text
    return r.json()["url"]


def _product(photos, **over):
    body = {
        "name": "1121 Steam Basmati",
        "category": "Rice",
        "quantity": "500",
        "moq": "25",
        "pricePerUnit": "72.50",
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
    assert (await client.post("/products", json=_product([url], pricePerUnit="-1"))).status_code == 422
    assert (await client.post("/products", json=_product([url], description="d" * 5001))).status_code == 422
    assert (await client.post("/products", json=_product([url], category="Gold"))).status_code == 422
    assert (await client.post("/products", json=_product([url], moq="600"))).status_code == 422  # moq > quantity
    assert (await client.post("/products", json=_product([url], currency="RUPEES"))).status_code == 422
    r = await client.post("/products", json=_product([]))
    assert r.status_code == 400 and "photo" in r.json()["detail"]
    r = await client.post("/products", json=_product(["https://evil.example/x.png"]))
    assert r.status_code == 400
    r = await client.post("/products", json=_product(["/uploads/products/" + "a" * 32 + ".png"]))
    assert r.status_code == 400  # well-formed but never uploaded
    many = [await _photo(client) for _ in range(6)]
    r = await client.post("/products", json=_product(many))
    assert r.status_code == 400 and "At most 5" in r.json()["detail"]

    r = await client.post("/products", json=_product([url, url]))
    assert r.status_code == 201, r.text
    assert r.json()["photos"] == [url]
    listed = (await client.get("/products")).json()
    assert len(listed) == 1 and listed[0]["pricePerUnit"] == "72.50" and listed[0]["currency"] == "INR"

    # Soft delete: gone from the business's list; only the owner business can delete.
    pid = listed[0]["id"]
    assert (await client.delete(f"/products/{pid}")).status_code == 204
    assert (await client.get("/products")).json() == []
    assert (await client.delete(f"/products/{pid}")).status_code == 404


async def test_market_visibility_is_business_level(client, make_client, admin_client):
    seller = await signup_and_login(client, "seller@kaverifoods.in")
    await fill_mandatory(client, n=1)
    url = await _photo(client)
    pid = (await client.post("/products", json=_product([url]))).json()["id"]

    anon = make_client()
    # Draft business → not in the market.
    assert (await anon.get("/public/products")).json()["total"] == 0
    assert (await anon.get(f"/public/products/{pid}")).status_code == 404

    await client.post("/me/submit-verification")
    assert (await anon.get("/public/products")).json()["total"] == 0  # pending is not enough
    assert (await admin_client.post(f"/admin/users/{seller['userId']}/verify")).status_code == 200

    listing = (await anon.get("/public/products?q=basmati")).json()
    assert listing["total"] == 1
    card = listing["items"][0]
    assert card["seller"]["businessName"] == "Acme Agro 1 Pvt Ltd"
    assert card["seller"]["sellerId"] == seller["businessId"]
    assert card["currency"] == "INR"
    assert "email" not in card["seller"]
    detail = (await anon.get(f"/public/products/{pid}")).json()
    assert detail["photos"] == [url]
    facets = (await anon.get("/public/catalog/facets")).json()
    assert facets["categories"] == [{"value": "Rice", "count": 1}]

    # Revoking the business hides its listings again.
    r = await admin_client.post(f"/admin/users/{seller['userId']}/reject", json={"reason": "Expired GST"})
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
    url = await _photo(client)
    pid = (await client.post("/products", json=_product([url]))).json()["id"]
    await client.post("/me/submit-verification")
    assert (await admin_client.post(f"/admin/users/{seller['userId']}/verify")).status_code == 200
    return seller, pid


async def test_contact_reveal_gates_and_idempotency(client, make_client, admin_client):
    seller, pid = await _verified_seller_with_product(client, admin_client)
    # Owner contact + business address in the reveal.
    r = await admin_client.patch(
        f"/admin/users/{seller['userId']}",
        json={"businessProfile": {"city": "Karnal", "state": "Haryana", "entityType": "private_ltd"}},
    )
    assert r.status_code == 200

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


async def test_reveal_limit_is_per_business(client, make_client, admin_client):
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
