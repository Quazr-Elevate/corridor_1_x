"""M1 listings: drafts, the submit checklist, review, edits to a published
listing, specifications, certificates and the admin queue (CX-071 … CX-075)."""
from __future__ import annotations

import sqlite3
import uuid
from datetime import timedelta

import pytest
from conftest import (
    PDF_BYTES,
    complete_listing,
    fill_mandatory,
    publish_listing,
    set_status,
    signup_and_login,
    upload_photo,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from test_migration_0020 import _alembic, _build_0019

from app.core.db import SessionLocal
from app.core.errors import Conflict
from app.core.time import utcnow
from app.models.admin_action import AdminAction
from app.models.business import BusinessStatus
from app.models.listing import CertificateDownload, ProductSpec
from app.models.product import ListingStatus, Product
from app.modules.catalog.lifecycle import transition


async def _seller(c, email="seller@kaverifoods.in", *, verified=True) -> dict:
    who = await signup_and_login(c, email)
    if verified:
        await set_status(who["userId"], BusinessStatus.verified)
    return who


async def _template(c, category="Rice") -> dict:
    return (await c.get("/public/catalog/template", params={"category": category})).json()


async def _cert_type(c, code="coa") -> str:
    return next(t["id"] for t in (await _template(c))["certificateTypes"] if t["code"] == code)


async def _add_cert(c, pid: str, type_id: str, content: bytes = PDF_BYTES):
    return await c.post(
        f"/products/{pid}/certificates",
        data={"certificateTypeId": type_id},
        files={"file": ("COA Kaveri Foods.pdf", content, "application/pdf")},
    )


# ── Lifecycle rules ──────────────────────────────────────────────────


def test_transition_allows_only_the_drawn_moves():
    S = ListingStatus
    allowed = {
        (S.draft, S.under_review), (S.rejected, S.under_review), (S.under_review, S.draft),
        (S.under_review, S.published), (S.under_review, S.rejected), (S.published, S.paused),
        (S.published, S.rejected), (S.paused, S.published), (S.paused, S.rejected),
    }
    now = utcnow()
    for src in S.ALL:
        for dst in S.ALL:
            product = Product(status=src)
            if (src, dst) in allowed:
                transition(product, dst, now=now, reason="x")
                assert product.status == dst
            else:
                with pytest.raises(Conflict):
                    transition(product, dst, now=now)
                assert product.status == src


async def test_a_draft_needs_only_a_name_and_category_and_lists_what_is_missing(client):
    await _seller(client, verified=False)
    r = await client.post("/products", json={"name": "Sona Masoori", "category": "Rice"})
    assert r.status_code == 201, r.text
    draft = r.json()
    assert draft["status"] == "draft" and draft["photos"] == [] and draft["specs"] == []
    assert "a description" in draft["missing"] and "at least one photo" in draft["missing"]
    assert "the specification “Moisture”" in draft["missing"]
    # Not in the market, and not submittable.
    r = await client.post(f"/products/{draft['id']}/submit")
    assert r.status_code == 403  # business not verified


async def test_submit_checklist_names_what_to_add(client):
    await _seller(client)
    draft = (await client.post("/products", json={"name": "Sona Masoori", "category": "Rice"})).json()
    r = await client.post(f"/products/{draft['id']}/submit")
    assert r.status_code == 400
    assert "a description" in r.json()["detail"] and "at least one incoterm" in r.json()["detail"]

    # A price validity date in the past doesn't count.
    listing = await complete_listing(client, priceValidUntil=(utcnow().date() - timedelta(days=1)).isoformat())
    r = await client.post(f"/products/{listing['id']}/submit")
    assert r.status_code == 400 and "hasn't passed" in r.json()["detail"]

    ready = await complete_listing(client)
    assert ready["missing"] == []
    r = await client.post(f"/products/{ready['id']}/submit")
    assert r.status_code == 200 and r.json()["status"] == "under_review"


async def test_review_flow_reject_fix_resubmit_approve(client, make_client, admin_client):
    await _seller(client)
    pid = (await complete_listing(client))["id"]
    anon = make_client()

    assert (await client.post(f"/products/{pid}/submit")).status_code == 200
    # While it is with the reviewer the seller can't edit, only withdraw.
    assert (await client.patch(f"/products/{pid}", json={"grade": "B"})).status_code == 409
    assert (await client.post(f"/products/{pid}/submit")).status_code == 409
    assert (await anon.get("/public/products")).json()["total"] == 0

    queue = (await admin_client.get("/admin/listings")).json()
    assert queue["total"] == 1 and queue["items"][0]["reviewKind"] == "new"
    assert queue["items"][0]["seller"]["legalName"]  # the desk sees who it is

    # Rejecting needs a reason; the seller sees it as written.
    assert (await admin_client.post(f"/admin/listings/{pid}/reject", json={})).status_code == 422
    r = await admin_client.post(f"/admin/listings/{pid}/reject", json={"reason": "Photo shows a company logo."})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    mine = (await client.get(f"/products/{pid}")).json()
    assert mine["status"] == "rejected" and mine["rejectionReason"] == "Photo shows a company logo."
    assert (await admin_client.get("/admin/listings")).json()["total"] == 0

    # Fix and resubmit.
    r = await client.patch(f"/products/{pid}", json={"photos": [await upload_photo(client)]})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    r = await client.post(f"/products/{pid}/submit")
    assert r.status_code == 200 and r.json()["rejectionReason"] is None
    r = await admin_client.post(f"/admin/listings/{pid}/approve")
    assert r.status_code == 200 and r.json() == {"id": pid, "status": "published", "hasPendingRevision": False}
    assert (await anon.get("/public/products")).json()["total"] == 1
    # Nothing left to decide.
    assert (await admin_client.post(f"/admin/listings/{pid}/approve")).status_code == 409

    async with SessionLocal() as db:
        actions = list(await db.scalars(select(AdminAction).order_by(AdminAction.created_at)))
    assert [a.action for a in actions] == ["listing.reject", "listing.approve"]
    assert actions[0].reason == "Photo shows a company logo." and actions[0].target_id == pid


async def test_withdraw_pause_resume(client, make_client, admin_client):
    await _seller(client)
    pid = (await complete_listing(client))["id"]
    assert (await client.post(f"/products/{pid}/pause")).status_code == 409  # not published
    assert (await client.post(f"/products/{pid}/submit")).status_code == 200
    r = await client.post(f"/products/{pid}/withdraw")
    assert r.status_code == 200 and r.json()["status"] == "draft"
    assert (await client.post(f"/products/{pid}/withdraw")).status_code == 409
    await publish_listing(client, admin_client, pid)

    anon = make_client()
    assert (await anon.get("/public/products")).json()["total"] == 1
    r = await client.post(f"/products/{pid}/pause")
    assert r.status_code == 200 and r.json()["status"] == "paused"
    assert (await anon.get("/public/products")).json()["total"] == 0
    assert (await anon.get(f"/public/products/{pid}")).status_code == 404
    r = await client.post(f"/products/{pid}/resume")
    assert r.status_code == 200 and r.json()["status"] == "published"
    assert (await anon.get("/public/products")).json()["total"] == 1  # no second review


async def test_a_stranger_cannot_touch_someone_elses_listing(client, make_client):
    await _seller(client)
    pid = (await complete_listing(client))["id"]
    stranger = make_client()
    await _seller(stranger, "other@othermill.in")
    for call in (
        stranger.get(f"/products/{pid}"),
        stranger.patch(f"/products/{pid}", json={"grade": "B"}),
        stranger.post(f"/products/{pid}/submit"),
        stranger.post(f"/products/{pid}/pause"),
        stranger.delete(f"/products/{pid}/revision"),
        stranger.delete(f"/products/{pid}"),
    ):
        assert (await call).status_code == 404
    assert (await make_client().get(f"/products/{pid}")).status_code == 401
    assert (await client.get(f"/products/{uuid.uuid4()}")).status_code == 404
    assert (await client.get("/products/not-a-uuid")).status_code == 404


# ── Editing a published listing (decision A-021) ─────────────────────


async def test_published_edit_price_goes_live_and_the_rest_waits_for_review(client, make_client, admin_client):
    await _seller(client)
    pid = (await complete_listing(client))["id"]
    await publish_listing(client, admin_client, pid)
    buyer = make_client()
    await _seller(buyer, "buyer@othermill.in")

    r = await client.patch(
        f"/products/{pid}",
        json={"priceMin": "75", "priceMax": "82", "quantity": "400", "name": "1121 Golden Sella", "grade": "Premium"},
    )
    assert r.status_code == 200, r.text
    mine = r.json()
    # Price and stock changed at once; the name and grade are only proposed.
    assert (mine["priceMin"], mine["priceMax"], mine["quantity"]) == ("75.00", "82.00", "400.00")
    assert (mine["name"], mine["grade"], mine["status"]) == ("1121 Steam Basmati", "Grade A", "published")
    assert mine["pendingRevision"] == {"name": "1121 Golden Sella", "grade": "Premium"}

    card = (await buyer.get(f"/public/products/{pid}")).json()
    assert (card["name"], card["grade"], card["priceMin"], card["priceMax"]) == ("1121 Steam Basmati", "Grade A", "75.00", "82.00")

    # The desk sees it as a revision, with what is live next to what was proposed.
    queue = (await admin_client.get("/admin/listings")).json()
    assert [(i["id"], i["reviewKind"]) for i in queue["items"]] == [(pid, "revision")]
    detail = (await admin_client.get(f"/admin/listings/{pid}")).json()
    assert {c["field"]: (c["current"], c["proposed"]) for c in detail["changes"]} == {
        "name": ("1121 Steam Basmati", "1121 Golden Sella"),
        "grade": ("Grade A", "Premium"),
    }

    # Setting a field back to the published value drops it from the revision.
    r = await client.patch(f"/products/{pid}", json={"grade": "Grade A"})
    assert r.json()["pendingRevision"] == {"name": "1121 Golden Sella"}

    r = await admin_client.post(f"/admin/listings/{pid}/approve")
    assert r.status_code == 200 and r.json()["hasPendingRevision"] is False
    card = (await buyer.get(f"/public/products/{pid}")).json()
    assert card["name"] == "1121 Golden Sella"
    assert (await client.get(f"/products/{pid}")).json()["pendingRevision"] is None


async def test_rejected_revision_keeps_the_published_version(client, make_client, admin_client):
    await _seller(client)
    pid = (await complete_listing(client))["id"]
    await publish_listing(client, admin_client, pid)
    anon = make_client()

    # A phone number never gets this far (the leak filter refuses it); a
    # request to be contacted directly is saved for the reviewer to judge.
    assert (await client.patch(f"/products/{pid}", json={"description": "Call me on 98765 43210"})).status_code == 400
    assert (await client.patch(f"/products/{pid}", json={"description": "WhatsApp me for samples"})).status_code == 200
    r = await admin_client.post(f"/admin/listings/{pid}/reject", json={"reason": "No contact details in the description."})
    assert r.status_code == 200 and r.json()["status"] == "published"
    mine = (await client.get(f"/products/{pid}")).json()
    assert mine["status"] == "published" and mine["pendingRevision"] is None
    assert mine["revisionRejectionReason"] == "No contact details in the description."
    assert mine["rejectionReason"] is None
    assert (await anon.get(f"/public/products/{pid}")).json()["description"] == "Aromatic long grain"

    # The seller can also drop their own pending edit.
    assert (await client.patch(f"/products/{pid}", json={"variety": "Pusa"})).json()["pendingRevision"] == {"variety": "Pusa"}
    assert (await client.delete(f"/products/{pid}/revision")).json()["pendingRevision"] is None
    assert (await admin_client.get("/admin/listings")).json()["total"] == 0

    # An edit that would leave the listing incomplete is refused up front.
    r = await client.patch(f"/products/{pid}", json={"photos": []})
    assert r.status_code == 400 and "at least one photo" in r.json()["detail"]

    # With nothing waiting, a reject takes the listing down.
    r = await admin_client.post(f"/admin/listings/{pid}/reject", json={"reason": "Stock no longer available."})
    assert r.json()["status"] == "rejected"
    assert (await anon.get(f"/public/products/{pid}")).status_code == 404


# ── Specifications (CX-073) ──────────────────────────────────────────


async def test_specs_follow_the_category_template(client, admin_client):
    await _seller(client)
    rice = await _template(client)
    assert [p["code"] for p in rice["specParameters"]] == ["moisture", "broken_grains", "foreign_matter", "grain_length"]
    moisture, length = rice["specParameters"][0], rice["specParameters"][3]
    spices = await _template(client, "Spices")

    draft = (await client.post("/products", json={"name": "Sona Masoori", "category": "Rice"})).json()
    url = f"/products/{draft['id']}"
    bad = [
        [{"parameterId": moisture["id"], "value": "twelve"}],  # a number is expected
        [{"parameterId": moisture["id"], "value": "-1"}],
        [{"parameterId": spices["specParameters"][1]["id"], "value": "2"}],  # another category's row
        [{"parameterId": str(uuid.uuid4()), "value": "2"}],
    ]
    for specs in bad:
        assert (await client.patch(url, json={"specs": specs})).status_code == 400
    assert (await client.patch(url, json={"specs": [{"parameterId": moisture["id"], "value": "1", "operator": "ABOUT"}]})).status_code == 422

    r = await client.patch(
        url,
        json={"specs": [
            {"parameterId": length["id"], "value": "6.50", "testMethod": "ISO 11746"},
            {"parameterId": moisture["id"], "value": "12", "operator": "EQ"},
        ]},
    )
    assert r.status_code == 200, r.text
    # Template order; the operator defaults to the parameter's.
    assert [(s["code"], s["value"], s["unit"], s["operator"], s["testMethod"]) for s in r.json()["specs"]] == [
        ("moisture", "12", "%", "EQ", None),
        ("grain_length", "6.5", "mm", "MIN", "ISO 11746"),
    ]
    assert "the specification “Broken grains”" in r.json()["missing"]

    # Changing the category drops rows that belong to the old template.
    r = await client.patch(url, json={"category": "Spices"})
    assert r.status_code == 200 and r.json()["specs"] == []
    async with SessionLocal() as db:
        assert list(await db.scalars(select(ProductSpec))) == []

    # An admin makes a Spices row required: the checklist follows.
    volatile = spices["specParameters"][1]
    r = await admin_client.patch(f"/admin/listing-templates/spec-parameters/{volatile['id']}", json={"isRequired": True})
    assert r.status_code == 200 and r.json()["isRequired"] is True
    assert "the specification “Volatile oil”" in (await client.get(url)).json()["missing"]


async def test_spec_changes_on_a_published_listing_wait_for_review(client, make_client, admin_client):
    await _seller(client)
    pid = (await complete_listing(client))["id"]
    await publish_listing(client, admin_client, pid)
    params = (await _template(client))["specParameters"]
    new_specs = [{"parameterId": p["id"], "value": "3"} for p in params]

    r = await client.patch(f"/products/{pid}", json={"specs": new_specs})
    assert r.status_code == 200
    assert [s["value"] for s in r.json()["specs"]] == ["5", "5", "5", "5"]  # still live
    assert [s["value"] for s in r.json()["pendingRevision"]["specs"]] == ["3", "3", "3", "3"]
    # Dropping a required row is refused.
    r = await client.patch(f"/products/{pid}", json={"specs": new_specs[:2]})
    assert r.status_code == 400 and "specification" in r.json()["detail"]

    assert (await admin_client.post(f"/admin/listings/{pid}/approve")).status_code == 200
    detail = (await make_client().get(f"/public/products/{pid}")).json()
    assert [(s["name"], s["value"]) for s in detail["specs"]][:2] == [("Moisture", "3"), ("Broken grains", "3")]


async def test_admin_manages_listing_templates(admin_client, client):
    r = await admin_client.post(
        "/admin/listing-templates/spec-parameters",
        json={"category": "Tea", "code": "Leaf_Grade", "name": "Leaf grade", "valueType": "text", "defaultOperator": "EQ"},
    )
    assert r.status_code == 201, r.text
    created = r.json()
    assert (created["code"], created["valueType"], created["unit"]) == ("leaf_grade", "text", None)
    dup = await admin_client.post(
        "/admin/listing-templates/spec-parameters", json={"category": "Tea", "code": "leaf_grade", "name": "Again"}
    )
    assert dup.status_code == 409
    assert (await admin_client.post("/admin/listing-templates/spec-parameters", json={"category": "Gold", "code": "x1", "name": "X one"})).status_code == 422

    listed = (await admin_client.get("/admin/listing-templates/spec-parameters", params={"category": "Tea"})).json()
    assert listed["total"] == 1 and listed["items"][0]["id"] == created["id"]

    # A text parameter takes text; retiring it removes it from the template.
    await _seller(client)
    r = await client.post("/products", json={"name": "Assam CTC", "category": "Tea", "specs": [{"parameterId": created["id"], "value": "BOP"}]})
    assert r.status_code == 201 and r.json()["specs"][0]["value"] == "BOP"
    r = await admin_client.patch(f"/admin/listing-templates/spec-parameters/{created['id']}", json={"active": False})
    assert r.json()["active"] is False
    assert (await _template(client, "Tea"))["specParameters"] == []
    assert (await admin_client.patch(f"/admin/listing-templates/spec-parameters/{uuid.uuid4()}", json={"active": True})).status_code == 404

    r = await admin_client.post(
        "/admin/listing-templates/certificate-types",
        json={"category": "Tea", "code": "tea_board", "name": "Tea Board registration", "isRequired": True},
    )
    assert r.status_code == 201, r.text
    types = (await admin_client.get("/admin/listing-templates/certificate-types", params={"category": "Tea"})).json()
    assert {t["code"] for t in types["items"]} == {"coa", "quality_test_report", "product_certificate", "tea_board"}
    r = await admin_client.patch(f"/admin/listing-templates/certificate-types/{r.json()['id']}", json={"name": "Tea Board licence"})
    assert r.json()["name"] == "Tea Board licence"

    async with SessionLocal() as db:
        actions = [a.action for a in await db.scalars(select(AdminAction).order_by(AdminAction.created_at))]
    assert actions == ["spec_parameter.create", "spec_parameter.update", "certificate_type.create", "certificate_type.update"]


# ── Certificates (CX-075) ────────────────────────────────────────────


async def test_certificates_are_internal_until_an_admin_approves_the_download(client, make_client, admin_client):
    await _seller(client)
    pid = (await complete_listing(client))["id"]
    coa = await _cert_type(client)

    assert (await _add_cert(client, pid, coa, b"<html>not a pdf</html>")).status_code == 415
    assert (await _add_cert(client, pid, str(uuid.uuid4()))).status_code == 400
    r = await _add_cert(client, pid, coa)
    assert r.status_code == 201, r.text
    cert = r.json()
    assert (cert["code"], cert["visibility"], cert["mimeType"]) == ("coa", "internal", "application/pdf")
    await publish_listing(client, admin_client, pid)

    buyer, guest, unverified = make_client(), make_client(), make_client()
    b = await _seller(buyer, "buyer@othermill.in")
    await _seller(unverified, "new@startup.in", verified=False)

    # Internal: the seller can open it, nobody else can, and the market doesn't list it.
    assert (await client.get(cert["url"])).content == PDF_BYTES
    assert (await buyer.get(cert["url"])).status_code == 404
    assert (await buyer.get(f"/public/products/{pid}")).json()["certificates"] == []

    r = await admin_client.post(f"/admin/listings/{pid}/certificates/{cert['id']}/visibility", json={"visibility": "public"})
    assert r.status_code == 422
    r = await admin_client.post(f"/admin/listings/{pid}/certificates/{cert['id']}/visibility", json={"visibility": "downloadable"})
    assert r.status_code == 200 and r.json()["visibility"] == "downloadable"

    # Downloadable: listed by type name only (the filename can name the seller).
    public = (await guest.get(f"/public/products/{pid}")).json()["certificates"]
    assert public == [{"id": cert["id"], "name": "Certificate of analysis (COA)", "url": cert["url"]}]
    assert "Kaveri" not in str(public)
    assert (await guest.get(cert["url"])).status_code == 401
    assert (await unverified.get(cert["url"])).status_code == 404
    r = await buyer.get(cert["url"])
    assert r.status_code == 200 and r.content == PDF_BYTES and r.headers["cache-control"] == "private, no-store"

    async with SessionLocal() as db:
        downloads = list(await db.scalars(select(CertificateDownload)))
    # Only the buyer's download is logged, against the buyer's business.
    assert [(str(d.certificate_id), str(d.buyer_business_id)) for d in downloads] == [(cert["id"], b["businessId"])]

    # Replacing the file sends it back to internal: the admin approved the old one.
    r = await _add_cert(client, pid, coa)
    assert r.status_code == 201 and r.json()["visibility"] == "internal" and r.json()["id"] == cert["id"]
    assert (await buyer.get(cert["url"])).status_code == 404

    # The admin's own view of the file is audited.
    r = await admin_client.get(f"/admin/listings/{pid}/certificates/{cert['id']}/file")
    assert r.status_code == 200 and r.content == PDF_BYTES
    async with SessionLocal() as db:
        actions = [a.action for a in await db.scalars(select(AdminAction).order_by(AdminAction.created_at))]
    assert actions[-2:] == ["listing.certificate_visibility", "listing.certificate_viewed"]

    # A paused listing's certificate is out of reach again.
    await admin_client.post(f"/admin/listings/{pid}/certificates/{cert['id']}/visibility", json={"visibility": "downloadable"})
    await client.post(f"/products/{pid}/pause")
    assert (await buyer.get(cert["url"])).status_code == 404

    assert (await client.delete(f"/products/{pid}/certificates/{cert['id']}")).status_code == 204
    assert (await client.get(cert["url"])).status_code == 404


async def test_a_required_certificate_blocks_submit(client, admin_client):
    await _seller(client)
    coa = await _cert_type(client)
    assert (await admin_client.patch(f"/admin/listing-templates/certificate-types/{coa}", json={"isRequired": True})).status_code == 200
    pid = (await complete_listing(client))["id"]
    r = await client.post(f"/products/{pid}/submit")
    assert r.status_code == 400 and "the document “Certificate of analysis (COA)”" in r.json()["detail"]
    assert (await _add_cert(client, pid, coa)).status_code == 201
    assert (await client.post(f"/products/{pid}/submit")).status_code == 200
    # Documents are frozen while the reviewer has the listing.
    assert (await _add_cert(client, pid, coa)).status_code == 409


# ── Admin access ─────────────────────────────────────────────────────


async def test_listing_review_needs_an_admin_with_the_permission(client, make_client, admin_client):
    await _seller(client)
    pid = (await complete_listing(client))["id"]
    assert (await client.post(f"/products/{pid}/submit")).status_code == 200
    # A trader session is not an admin session.
    assert (await client.get("/admin/listings")).status_code == 401
    assert (await client.post(f"/admin/listings/{pid}/approve")).status_code == 401
    assert (await make_client().get(f"/admin/listings/{pid}")).status_code == 401
    assert (await admin_client.get(f"/admin/listings/{uuid.uuid4()}")).status_code == 404
    everything = (await admin_client.get("/admin/listings", params={"queue": "all", "status": "under_review"})).json()
    assert everything["total"] == 1
    assert (await admin_client.get("/admin/listings", params={"queue": "all", "status": "nope"})).status_code == 400


# ── Database rules and migration ─────────────────────────────────────


async def test_database_refuses_bad_status_and_price_range(client):
    await _seller(client)
    pid = uuid.UUID((await complete_listing(client))["id"])
    for values, constraint in (
        ({"status": "live"}, "ck_products_status"),
        ({"price_max": 1}, "ck_products_price_range"),
        ({"lead_time_days": -1}, "ck_products_lead_time"),
    ):
        async with SessionLocal() as db:
            product = await db.get(Product, pid)
            for key, value in values.items():
                setattr(product, key, value)
            with pytest.raises(IntegrityError, match=constraint):
                await db.commit()


def test_0026_publishes_listings_that_were_already_live(tmp_path):
    db = tmp_path / "v25.db"
    _build_0019(db)
    assert _alembic(db, "upgrade", "0025_totp_columns").returncode == 0
    con = sqlite3.connect(db)
    businesses = dict(con.execute("SELECT verification_status, id FROM businesses WHERE deleted_at IS NULL"))
    assert "verified" in businesses, "the 0019 fixture needs a verified business"
    other = next(bid for status, bid in businesses.items() if status != "verified")
    rows = [
        ("live", businesses["verified"], "Rice", "Haryana", 100, None),
        ("hidden", other, "Rice", None, None, None),
        ("deleted", businesses["verified"], "Rice", None, 50, "2026-01-01"),
    ]
    for name, business, category, state, price, deleted in rows:
        con.execute(
            "INSERT INTO products (id, business_id, name, category, unit, currency, photos, origin_state, "
            "price_per_unit, price_usd, deleted_at) VALUES (?, ?, ?, ?, 'MT', 'INR', '[]', ?, ?, ?, ?)",
            (uuid.uuid4().hex, business, f"{name} lot", category, state, price, price, deleted),
        )
    con.commit()
    before = con.execute("SELECT count(*) FROM products").fetchone()[0]
    con.close()

    proc = _alembic(db, "upgrade", "0026_listing_review")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    got = {
        r[0]: r[1:]
        for r in con.execute("SELECT name, status, published_at IS NOT NULL, price_max, origin_country FROM products")
    }
    assert got["live lot"] == ("published", 1, 100, "IN")
    assert got["hidden lot"] == ("draft", 0, None, None)
    assert got["deleted lot"][0] == "draft"
    assert con.execute("SELECT count(*) FROM spec_parameters WHERE category = 'Rice' AND is_required").fetchone()[0] == 4
    assert con.execute("SELECT count(*) FROM certificate_types").fetchone()[0] == 3
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("UPDATE products SET status = 'live'")
    con.close()

    proc = _alembic(db, "downgrade", "0025_totp_columns")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert not {"spec_parameters", "product_specs", "certificate_types", "product_certificates"} & tables
    assert "status" not in {r[1] for r in con.execute("PRAGMA table_info(products)")}
    assert con.execute("SELECT count(*) FROM products").fetchone()[0] == before  # no listing lost
    con.close()
