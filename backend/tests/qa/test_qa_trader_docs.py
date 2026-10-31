"""QA-300 / 400 / 500 — Trader documents, replacement, submit gate (adapted).

Pegan's ``GET /me/verification-docs/requirements`` maps to main's
``GET /kyb/document-types`` (the business's country) + the entry list.
Adapted: a second add for the same type is refused (409) and the file is
replaced by editing the entry (PATCH) — still at most one row per type.
``mandatoryTotal`` = 4 profile fields + required documents of the country.
"""
from __future__ import annotations

from conftest import fill_mandatory, signup_and_login
from qa_helpers import TINY_PNG, admin_add_doc_type, set_country, uniq, uniq_code, upload_entry


async def _signup(client, country: str = "IN") -> str:
    email = f"{uniq('qa3')}@test.cor1x.co"
    await signup_and_login(client, email)
    if country != "IN":
        assert (await set_country(client, country)).status_code == 200
    return email


# QA-300.1 — unauthenticated → 401
async def test_document_list_requires_auth(make_client):
    assert (await make_client().get("/kyb/document-types")).status_code == 401


# QA-300.2 — a new type shows up for traders in that country
async def test_new_type_visible_to_trader(client, admin_client):
    await _signup(client)
    code = uniq_code("qa300")
    await admin_add_doc_type(admin_client, code=code, name="QA300 Doc")
    hit = {t["code"]: t for t in (await client.get("/kyb/document-types")).json()}[code]
    assert hit["name"] == "QA300 Doc" and hit["isMandatory"] is True


# QA-300.3 — an India type is not offered to a UAE trader
async def test_other_country_type_not_visible(client, admin_client, make_client):
    await _signup(client)
    code = uniq_code("qa300iso")
    await admin_add_doc_type(admin_client, code=code, name="India-only")
    uae = make_client()
    await _signup(uae, country="AE")
    assert all(t["code"] != code for t in (await uae.get("/kyb/document-types")).json())


# QA-400.1 — upload fills the type; response and list carry code + name
async def test_upload_fills_type_and_name(client, admin_client):
    await _signup(client)
    code = uniq_code("qa400")
    t = await admin_add_doc_type(admin_client, code=code, name="QA400 Doc")
    doc = await upload_entry(client, type_id=t["id"])
    assert doc["documentTypeCode"] == code and doc["certType"] == "QA400 Doc"
    hits = [d for d in (await client.get("/me/verification-docs")).json() if d["documentTypeCode"] == code]
    assert len(hits) == 1 and hits[0]["certType"] == "QA400 Doc"


# QA-400.2 — replacing the file keeps one row per type
async def test_replace_file_keeps_one_row(client, admin_client):
    await _signup(client)
    code = uniq_code("qa400rep")
    t = await admin_add_doc_type(admin_client, code=code, name="QA400 replace")
    first = await upload_entry(client, type_id=t["id"], filename="first.png")
    r = await client.post(
        "/me/verification-docs", data={"documentTypeId": t["id"]}, files={"file": ("second.png", TINY_PNG, "image/png")}
    )
    assert r.status_code == 409 and "edit that entry" in r.json()["detail"]
    r = await client.patch(f"/me/verification-docs/{first['id']}", files={"file": ("second.png", TINY_PNG, "image/png")})
    assert r.status_code == 200 and r.json()["filename"] == "second.png"
    docs = [d for d in (await client.get("/me/verification-docs")).json() if d["documentTypeCode"] == code]
    assert len(docs) == 1 and docs[0]["filename"] == "second.png"


# QA-400.3 — another country's type is refused
async def test_cross_country_type_rejected(client, admin_client):
    await _signup(client)
    t = await admin_add_doc_type(admin_client, country="AE", code=uniq_code("qa400ae"), name="AE only")
    r = await client.post(
        "/me/verification-docs", data={"documentTypeId": t["id"]}, files={"file": ("cert.png", TINY_PNG, "image/png")}
    )
    assert r.status_code == 400 and "country" in r.json()["detail"]


# QA-400.4 — unknown type id is refused
async def test_unknown_type_rejected(client):
    await _signup(client)
    r = await client.post(
        "/me/verification-docs",
        data={"documentTypeId": "00000000-0000-0000-0000-000000000000"},
        files={"file": ("cert.png", TINY_PNG, "image/png")},
    )
    assert r.status_code == 400


# QA-500.1 — submit before a required document → 400 naming it
async def test_submit_blocked_without_required_docs(client, admin_client):
    await _signup(client)
    await fill_mandatory(client)  # profile + GSTIN + PAN
    await admin_add_doc_type(admin_client, code=uniq_code("qa500"), name="Required for QA500")
    r = await client.post("/me/submit-verification")
    assert r.status_code == 400 and "Required for QA500" in r.json()["detail"]


# QA-500.2 — once added, submit lands with the right state
async def test_submit_success_once_all_filled(client, admin_client):
    await _signup(client)
    await fill_mandatory(client)
    t = await admin_add_doc_type(admin_client, code=uniq_code("qa500ok"), name="QA500 OK")
    await upload_entry(client, type_id=t["id"])
    r = await client.post("/me/submit-verification")
    assert r.status_code == 200
    state = r.json()
    assert state["status"] == "pending_verification" and state["missing"] == []
    assert state["mandatoryTotal"] == 4 + 3  # profile fields + GSTIN, PAN, QA500 OK


# QA-500.3 — mandatoryTotal follows the live list
async def test_mandatory_total_tracks_catalog(client, admin_client):
    await _signup(client)
    before = (await client.get("/me")).json()["verification"]["mandatoryTotal"]
    await admin_add_doc_type(admin_client, code=uniq_code("qa500live"), name="live")
    after = (await client.get("/me")).json()["verification"]["mandatoryTotal"]
    assert after == before + 1
