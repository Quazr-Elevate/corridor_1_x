"""KYB profile: sign-up with company name, document-type dropdown, encrypted
entries, reveal, cross-business access, submission rules, country change,
branding images, quick tour, admin reveal audit and the admin type editor."""
from __future__ import annotations

import base64
import logging
import uuid

import pytest
from conftest import PDF_BYTES, png_bytes, signup_and_login
from sqlalchemy import select

from app.core import crypto
from app.core.config import Settings
from app.core.db import SessionLocal
from app.models.admin_action import AdminAction
from app.models.business_document import BusinessDocument

GSTIN = "29ABCDE1234F1Z5"
PAN = "ABCDE1234F"


async def _types(c, country: str | None = None) -> dict[str, dict]:
    q = f"?country={country}" if country else ""
    r = await c.get(f"/kyb/document-types{q}")
    assert r.status_code == 200, r.text
    return {t["code"]: t for t in r.json()}


async def _add(c, *, type_id=None, name=None, value=None, file: bytes | None = None, filename="doc.pdf"):
    data = {}
    if type_id:
        data["documentTypeId"] = type_id
    if name:
        data["customName"] = name
    if value is not None:
        data["value"] = value
    files = {"file": (filename, file, "application/pdf")} if file is not None else None
    return await c.post("/me/verification-docs", data=data, files=files)


async def _profile(c, **over):
    body = {"legalName": "Kaveri Foods Pvt Ltd", "country": "IN", "addressLine": "12 Mill Road", "city": "Karnal"}
    body.update(over)
    return await c.put("/me/business-profile", json=body)


# ── sign-up ──────────────────────────────────────────────────────────


async def test_signup_names_the_business_and_country_defaults(client, make_client):
    login = await signup_and_login(client, "owner@kaverifoods.in", company_name="Kaveri Foods Pvt Ltd")
    assert login["businessName"] == "Kaveri Foods Pvt Ltd"
    me = (await client.get("/me")).json()
    assert me["business"]["country"] == "IN" and me["showTour"] is True
    assert me["branding"] == {"logoUrl": None, "bannerUrl": None}

    # Company names are unique (case / spacing ignored).
    other = make_client()
    with pytest.raises(AssertionError, match="already registered"):
        await signup_and_login(other, "x@otherfoods.in", company_name="kaveri  foods pvt ltd")


# ── dropdown ─────────────────────────────────────────────────────────


async def test_dropdown_follows_country(client):
    await signup_and_login(client, "t@kaverifoods.in")
    india = await _types(client)
    assert list(india) == ["gstin", "pan", "udyam", "iec", "fssai"]
    assert india["gstin"]["isMandatory"] and india["gstin"]["needsValue"] and not india["gstin"]["needsFile"]
    assert india["fssai"]["needsValue"] and india["fssai"]["needsFile"]
    assert "aadhaar" not in india
    uae = await _types(client, "AE")
    assert list(uae) == ["trade_licence", "trn"] and uae["trade_licence"]["needsFile"]


# ── entries ──────────────────────────────────────────────────────────


async def test_value_is_encrypted_masked_and_revealable(client, caplog):
    await signup_and_login(client, "enc@kaverifoods.in")
    t = await _types(client)
    caplog.set_level(logging.DEBUG)
    r = await _add(client, type_id=t["gstin"]["id"], value=" 29abcde1234f1z5 ")
    assert r.status_code == 201, r.text
    entry = r.json()
    assert entry["valueMasked"] == "••••F1Z5" and entry["hasValue"] and not entry["hasFile"]
    assert entry["certType"] == "GSTIN" and entry["documentTypeCode"] == "gstin" and not entry["isOther"]
    assert entry["status"] == "pending" and entry["url"] is None
    assert GSTIN not in r.text
    listing = await client.get("/me/verification-docs")
    assert GSTIN not in listing.text and GSTIN not in (await client.get("/me")).text

    # Stored as ciphertext under the current key (v2), with hash + hint.
    async with SessionLocal() as db:
        row = await db.get(BusinessDocument, uuid.UUID(entry["id"]))
    assert GSTIN not in row.value_encrypted and row.value_key_version == 2
    assert len(row.value_hash) == 64 and row.value_last4 == "F1Z5" and row.value_unique is True
    assert crypto.decrypt(row.value_encrypted, 2) == GSTIN

    r = await client.post(f"/me/verification-docs/{entry['id']}/reveal")
    assert r.status_code == 200 and r.json()["value"] == GSTIN
    # Never in the logs.
    assert GSTIN not in caplog.text and "29abcde1234f1z5" not in caplog.text


async def test_entry_validation(client):
    await signup_and_login(client, "val@kaverifoods.in")
    t = await _types(client)
    uae = await _types(client, "AE")

    r = await _add(client, type_id=t["gstin"]["id"], value="12345")
    assert r.status_code == 400 and "valid GSTIN" in r.json()["detail"]
    r = await _add(client, type_id=t["gstin"]["id"])
    assert r.status_code == 400 and "Enter the GSTIN" in r.json()["detail"]
    r = await _add(client, type_id=uae["trn"]["id"], value="100000000000003")
    assert r.status_code == 400 and "country" in r.json()["detail"]
    r = await _add(client, type_id=t["pan"]["id"], name="Something", value=PAN)
    assert r.status_code == 400
    r = await _add(client, type_id=str(uuid.uuid4()), value=PAN)
    assert r.status_code == 400

    # value_and_file needs both.
    r = await _add(client, type_id=t["fssai"]["id"], value="12345678901234")
    assert r.status_code == 400 and "Upload a copy" in r.json()["detail"]
    r = await _add(client, type_id=t["fssai"]["id"], value="12345678901234", file=PDF_BYTES)
    assert r.status_code == 201 and r.json()["hasFile"] and r.json()["hasValue"]

    # Other: needs a name and a value or a file; never Aadhaar.
    assert (await _add(client, name="Spice Board", file=None)).status_code == 400
    r = await _add(client, name="Aadhaar card", value="123412341234")
    assert r.status_code == 400 and "Aadhaar" in r.json()["detail"]
    r = await _add(client, name="Spice Board registration", file=PDF_BYTES)
    assert r.status_code == 201 and r.json()["isOther"] and r.json()["url"].endswith("/file")
    # Disguised files are refused.
    r = await _add(client, name="Other cert", file=b"<html>hi</html>", filename="a.pdf")
    assert r.status_code == 415

    # One entry per type.
    assert (await _add(client, type_id=t["pan"]["id"], value=PAN)).status_code == 201
    r = await _add(client, type_id=t["pan"]["id"], value="ZZZZZ9999Z")
    assert r.status_code == 409 and "edit that entry" in r.json()["detail"]


async def test_same_gstin_cannot_belong_to_two_businesses(client, make_client, admin_client):
    await signup_and_login(client, "a@kaverifoods.in")
    t = await _types(client)
    assert (await _add(client, type_id=t["gstin"]["id"], value=GSTIN)).status_code == 201

    other = make_client()
    await signup_and_login(other, "b@othermill.in")
    r = await _add(other, type_id=t["gstin"]["id"], value="29abcde 1234f1z5")  # case + spacing ignored
    assert r.status_code == 409 and "already registered" in r.json()["detail"]

    # A rejected claim stops blocking the real owner.
    first = (await client.get("/me/verification-docs")).json()[0]
    assert (await admin_client.post(f"/admin/docs/{first['id']}/reject", json={"reason": "Not yours"})).status_code == 200
    assert (await _add(other, type_id=t["gstin"]["id"], value=GSTIN)).status_code == 201


async def test_other_business_cannot_touch_entries(client, make_client):
    await signup_and_login(client, "own@kaverifoods.in")
    t = await _types(client)
    entry = (await _add(client, type_id=t["fssai"]["id"], value="12345678901234", file=PDF_BYTES)).json()

    stranger = make_client()
    await signup_and_login(stranger, "s@othermill.in")
    base = f"/me/verification-docs/{entry['id']}"
    assert (await stranger.get("/me/verification-docs")).json() == []
    assert (await stranger.post(f"{base}/reveal")).status_code == 404
    assert (await stranger.get(f"{base}/file")).status_code == 404
    assert (await stranger.patch(base, data={"value": "99999999999999"})).status_code == 404
    assert (await stranger.delete(base)).status_code == 404
    anon = make_client()
    assert (await anon.post(f"{base}/reveal")).status_code == 401
    assert (await anon.get("/kyb/document-types")).status_code == 401
    assert (await anon.post(f"/admin/docs/{entry['id']}/reveal")).status_code == 401
    # Still intact for the owner.
    assert (await client.post(f"{base}/reveal")).json()["value"] == "12345678901234"


async def test_update_entry_goes_back_to_review(client, admin_client):
    await signup_and_login(client, "upd@kaverifoods.in")
    t = await _types(client)
    entry = (await _add(client, type_id=t["fssai"]["id"], value="12345678901234", file=PDF_BYTES)).json()
    assert (await admin_client.post(f"/admin/docs/{entry['id']}/reject", json={"reason": "Expired"})).status_code == 200

    base = f"/me/verification-docs/{entry['id']}"
    assert (await client.patch(base, data={})).status_code == 400
    assert (await client.patch(base, data={"removeFile": "true"})).status_code == 400  # FSSAI needs the file
    assert (await client.patch(base, data={"customName": "x"})).status_code == 400  # only Other renames
    r = await client.patch(base, data={"value": "99999999999999"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "pending" and body["rejectionReason"] is None and body["valueMasked"] == "••••9999"
    r = await client.patch(base, files={"file": ("new.pdf", PDF_BYTES, "application/pdf")})
    assert r.status_code == 200 and r.json()["filename"] == "new.pdf"

    assert (await client.delete(base)).status_code == 204
    assert (await client.get("/me/verification-docs")).json() == []


# ── submission ───────────────────────────────────────────────────────


async def test_submission_needs_profile_and_mandatory_documents(client):
    await signup_and_login(client, "sub@kaverifoods.in", company_name="Sub Foods Pvt Ltd")
    me = (await client.get("/me")).json()
    v = me["verification"]
    assert v["missing"] == ["addressLine", "city", "kyb:gstin", "kyb:pan"]
    assert v["missingLabels"] == ["Registered address", "City", "GSTIN", "PAN"] and v["mandatoryTotal"] == 6
    r = await client.post("/me/submit-verification")
    assert r.status_code == 400 and "GSTIN" in r.json()["detail"]

    assert (await _profile(client, legalName="Sub Foods Pvt Ltd")).status_code == 200
    t = await _types(client)
    await _add(client, type_id=t["gstin"]["id"], value=GSTIN)
    assert (await client.get("/me")).json()["verification"]["missing"] == ["kyb:pan"]
    await _add(client, type_id=t["pan"]["id"], value=PAN)
    r = await client.post("/me/submit-verification")
    assert r.status_code == 200 and r.json()["status"] == "pending_verification" and r.json()["missing"] == []


async def test_country_change_switches_the_document_list(client):
    await signup_and_login(client, "uae@trader.ae")
    t = await _types(client)
    entry = (await _add(client, type_id=t["gstin"]["id"], value=GSTIN)).json()

    r = await _profile(client, legalName="Gulf Grain LLC", country="AE", city="Dubai")
    assert r.status_code == 400 and "GSTIN" in r.json()["detail"]
    await client.delete(f"/me/verification-docs/{entry['id']}")
    r = await _profile(client, legalName="Gulf Grain LLC", country="AE", city="Dubai", pincode=None)
    assert r.status_code == 200, r.text
    assert r.json()["business"]["country"] == "AE"
    assert list(await _types(client)) == ["trade_licence", "trn"]
    assert r.json()["verification"]["missing"] == ["kyb:trade_licence"]


# ── branding + tour ──────────────────────────────────────────────────


async def test_logo_banner_and_tour(client, make_client):
    await signup_and_login(client, "brand@kaverifoods.in")
    r = await client.post("/me/business/logo", files={"file": ("logo.png", png_bytes(), "image/png")})
    assert r.status_code == 201, r.text
    logo = r.json()["url"]
    assert logo.startswith("/uploads/branding/")
    r = await client.post("/me/business/banner", files={"file": ("b.png", png_bytes(8), "image/png")})
    banner = r.json()["url"]
    me = (await client.get("/me")).json()
    assert me["branding"] == {"logoUrl": logo, "bannerUrl": banner}
    pub = await make_client().get(logo)  # public, no session
    assert pub.status_code == 200 and pub.headers["content-type"] == "image/png"
    assert (await client.post("/me/business/logo", files={"file": ("x.pdf", PDF_BYTES, "application/pdf")})).status_code == 415
    assert (await client.post("/me/business/avatar", files={"file": ("l.png", png_bytes(), "image/png")})).status_code == 422

    # Replacing removes the old file; deleting clears it.
    new_logo = (await client.post("/me/business/logo", files={"file": ("l2.png", png_bytes(6), "image/png")})).json()["url"]
    assert (await make_client().get(logo)).status_code == 404
    assert (await client.delete("/me/business/logo")).status_code == 204
    assert (await make_client().get(new_logo)).status_code == 404
    assert (await client.get("/me")).json()["branding"]["logoUrl"] is None

    assert (await client.patch("/me", json={"tourCompleted": True})).json()["showTour"] is False
    assert (await client.patch("/me", json={"tourCompleted": False})).json()["showTour"] is True


# ── admin ────────────────────────────────────────────────────────────


async def test_admin_reveal_is_audited_without_the_value(client, admin_client):
    await signup_and_login(client, "aud@kaverifoods.in")
    t = await _types(client)
    entry = (await _add(client, type_id=t["gstin"]["id"], value=GSTIN)).json()
    r = await admin_client.post(f"/admin/docs/{entry['id']}/reveal")
    assert r.status_code == 200 and r.json()["value"] == GSTIN
    async with SessionLocal() as db:
        rows = list(await db.scalars(select(AdminAction)))
    assert [a.action for a in rows] == ["kyb.value_viewed"]
    assert GSTIN not in str(rows[0].details) and rows[0].target_id == entry["id"]


async def test_admin_manages_document_types(client, admin_client):
    r = await admin_client.post(
        "/admin/kyb/document-types",
        json={"country": "IN", "code": "spice_board", "name": "Spices Board registration", "inputKind": "value_or_file",
              "isMandatory": False, "sortOrder": 60},
    )
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["active"] and created["isUnique"]
    dup = await admin_client.post(
        "/admin/kyb/document-types", json={"country": "IN", "code": "spice_board", "name": "Dup", "inputKind": "file"}
    )
    assert dup.status_code == 409
    for bad in ({"code": "aadhaar", "name": "ID"}, {"code": "uid", "name": "Aadhar card"},
                {"code": "x1", "name": "Bad", "valuePattern": "[unclosed"}):
        body = {"country": "IN", "inputKind": "value"} | bad
        assert (await admin_client.post("/admin/kyb/document-types", json=body)).status_code == 422

    await signup_and_login(client, "types@kaverifoods.in")
    assert "spice_board" in await _types(client)
    r = await admin_client.patch(f"/admin/kyb/document-types/{created['id']}", json={"active": False, "isMandatory": True})
    assert r.status_code == 200 and r.json()["active"] is False
    assert "spice_board" not in await _types(client)  # hidden from the dropdown
    all_in = (await admin_client.get("/admin/kyb/document-types?country=IN")).json()
    assert "spice_board" in {x["code"] for x in all_in}

    # Users can't use the admin editor.
    assert (await client.get("/admin/kyb/document-types")).status_code == 401
    async with SessionLocal() as db:
        actions = [a.action for a in await db.scalars(select(AdminAction).order_by(AdminAction.created_at))]
    assert actions == ["kyb_type.create", "kyb_type.update"]


# ── crypto config ────────────────────────────────────────────────────


def _k(byte: bytes) -> str:
    return base64.b64encode(byte * 32).decode()


def test_key_config_and_rotation():
    with pytest.raises(crypto.CryptoConfigError):
        crypto.load_keys(Settings(debug=False, kyb_enc_keys="", kyb_hash_key=""))
    with pytest.raises(crypto.CryptoConfigError):
        crypto.load_keys(Settings(debug=False, kyb_enc_keys="1:short", kyb_hash_key=_k(b"h")))
    with pytest.raises(crypto.CryptoConfigError):
        crypto.load_keys(Settings(debug=False, kyb_enc_keys=f"1:{_k(b'a')}", kyb_hash_key=_k(b"a")))
    assert crypto.load_keys(Settings(debug=True, kyb_enc_keys="", kyb_hash_key="")).is_dev
    keys = crypto.load_keys(Settings(debug=False, kyb_enc_keys=f"1:{_k(b'a')},3:{_k(b'b')}", kyb_hash_key=_k(b"h")))
    assert keys.current == 3 and set(keys.enc) == {1, 3}

    # Values written under the old key (v1 in the test config) still decrypt.
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = b"\0" * 12
    old = base64.b64encode(nonce + AESGCM(b"k" * 32).encrypt(nonce, b"AAAAA1111A", b"cor1x-kyb-v1")).decode()
    assert crypto.decrypt(old, 1) == "AAAAA1111A"
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt(old, 2)  # wrong key slot is rejected (bound as associated data)
