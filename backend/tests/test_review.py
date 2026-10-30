"""Combined KYB review: countries set up by admins (with ≥ 1 required
document), per-item rejection, approval cascading to documents, and
verified businesses going back to review when KYB data changes."""
from __future__ import annotations

from conftest import fill_mandatory, signup_and_login
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.admin_action import AdminAction


async def _types(c) -> dict[str, dict]:
    return {t["code"]: t for t in (await c.get("/kyb/document-types")).json()}


async def _submitted(client, admin_client, *, email="r@kaverifoods.in", n=1, verify=False) -> dict:
    body = await signup_and_login(client, email)
    await fill_mandatory(client, n=n)
    assert (await client.post("/me/submit-verification")).status_code == 200
    if verify:
        assert (await admin_client.post(f"/admin/users/{body['userId']}/verify")).status_code == 200
    return body


# ── countries ────────────────────────────────────────────────────────


async def test_only_set_up_countries_can_be_picked(client):
    await signup_and_login(client, "c@kaverifoods.in")
    countries = (await client.get("/kyb/countries")).json()
    assert [c["code"] for c in countries] == ["IN", "AE"]  # by name: India, United Arab Emirates
    india = countries[0]
    assert india["name"] == "India" and india["defaultCurrency"] == "INR" and india["postalLabel"] == "PIN code"
    r = await client.put(
        "/me/business-profile", json={"legalName": "C Foods Pvt Ltd", "country": "SA", "addressLine": "1 Road", "city": "Riyadh"}
    )
    assert r.status_code == 400 and "doesn’t onboard" in r.json()["detail"]


async def test_admin_adds_country_with_required_documents(client, admin_client):
    doc = {"code": "cr", "name": "Commercial registration", "inputKind": "value_and_file", "isMandatory": True}
    # At least one required document; distinct codes; never Aadhaar.
    r = await admin_client.post("/admin/kyb/countries", json={"country": "SA", "documents": [doc | {"isMandatory": False}]})
    assert r.status_code == 422 and "at least one document as required" in r.text
    assert (await admin_client.post("/admin/kyb/countries", json={"country": "SA", "documents": []})).status_code == 422
    assert (await admin_client.post("/admin/kyb/countries", json={"country": "SA", "documents": [doc, doc]})).status_code == 422
    r = await admin_client.post(
        "/admin/kyb/countries",
        json={"country": "SA", "documents": [doc, {"code": "vat", "name": "VAT certificate", "inputKind": "file", "isMandatory": False}]},
    )
    assert r.status_code == 201, r.text
    assert [d["code"] for d in r.json()] == ["cr", "vat"]
    assert (await admin_client.post("/admin/kyb/countries", json={"country": "SA", "documents": [doc]})).status_code == 409
    # Single types can only join a country that's already set up.
    r = await admin_client.post("/admin/kyb/document-types", json={"country": "QA", "code": "cr", "name": "CR", "inputKind": "file"})
    assert r.status_code == 400 and "Add QA as a country first" in r.json()["detail"]

    await signup_and_login(client, "sa@gulfgrain.sa")
    assert "SA" in [c["code"] for c in (await client.get("/kyb/countries")).json()]
    r = await client.put(
        "/me/business-profile",
        json={"legalName": "Gulf Grain Co", "country": "SA", "addressLine": "1 Olaya St", "city": "Riyadh"},
    )
    assert r.status_code == 200 and r.json()["verification"]["missing"] == ["kyb:cr"]


async def test_last_required_document_is_protected(admin_client):
    types = {t["code"]: t for t in (await admin_client.get("/admin/kyb/document-types?country=AE")).json()}
    lic = types["trade_licence"]  # the only required AE document
    for patch in ({"isMandatory": False}, {"active": False}):
        r = await admin_client.patch(f"/admin/kyb/document-types/{lic['id']}", json=patch)
        assert r.status_code == 400 and "last required document" in r.json()["detail"]
    # Once another document is required, it can be relaxed.
    assert (await admin_client.patch(f"/admin/kyb/document-types/{types['trn']['id']}", json={"isMandatory": True})).status_code == 200
    assert (await admin_client.patch(f"/admin/kyb/document-types/{lic['id']}", json={"isMandatory": False})).status_code == 200


# ── review ───────────────────────────────────────────────────────────


async def test_reject_flags_items_and_rejects_those_documents(client, admin_client):
    body = await _submitted(client, admin_client)
    uid = body["userId"]
    r = await admin_client.post(f"/admin/users/{uid}/reject", json={"reason": "x", "failedItems": ["nope"]})
    assert r.status_code == 400 and "Unknown item" in r.json()["detail"]
    r = await admin_client.post(
        f"/admin/users/{uid}/reject",
        json={"reason": "GSTIN doesn't match the address", "failedItems": ["addressLine", "kyb:gstin", "addressLine"]},
    )
    assert r.status_code == 200, r.text

    me = (await client.get("/me")).json()
    assert me["verification"]["status"] == "rejected"
    assert me["verification"]["rejectedItems"] == ["addressLine", "kyb:gstin"]
    assert me["verification"]["rejectedItemLabels"] == ["Registered address", "GSTIN"]
    assert "kyb:gstin" in me["verification"]["missing"]  # a rejected required document no longer counts
    docs = {d["documentTypeCode"]: d for d in (await client.get("/me/verification-docs")).json()}
    assert docs["gstin"]["status"] == "rejected" and docs["gstin"]["rejectionReason"] == "GSTIN doesn't match the address"
    assert docs["pan"]["status"] == "pending"
    detail = (await admin_client.get(f"/admin/users/{uid}")).json()
    assert detail["verificationRejectedItems"] == ["addressLine", "kyb:gstin"]
    # A flagged required document must be fixed before anyone can approve.
    r = await admin_client.post(f"/admin/users/{uid}/verify")
    assert r.status_code == 400 and "GSTIN" in r.json()["detail"]

    # Fix + resubmit clears the flags.
    await client.patch(f"/me/verification-docs/{docs['gstin']['id']}", data={"value": "01AAAAA0001A1Z5"})
    assert (await client.post("/me/submit-verification")).status_code == 200
    assert (await client.get("/me")).json()["verification"]["rejectedItems"] == []


async def test_reject_needs_at_least_one_item(client, admin_client):
    body = await _submitted(client, admin_client)
    r = await admin_client.post(f"/admin/users/{body['userId']}/reject", json={"reason": "Fix it", "failedItems": []})
    assert r.status_code == 422
    r = await admin_client.post(f"/admin/users/{body['userId']}/reject", json={"reason": "Fix it"})
    assert r.status_code == 422


async def test_other_entries_are_labelled_and_decided_separately(client, admin_client):
    body = await signup_and_login(client, "lab@kaverifoods.in")
    await fill_mandatory(client)
    t = await _types(client)
    other = (await client.post("/me/verification-docs", data={"customName": "Spices Board registration", "value": "SB-12345"})).json()
    iec = (await client.post("/me/verification-docs", data={"documentTypeId": t["iec"]["id"], "value": "AAACS1234K"})).json()
    assert (await client.post("/me/submit-verification")).status_code == 200

    # Approving the business approves only the required documents.
    assert (await admin_client.post(f"/admin/users/{body['userId']}/verify")).status_code == 200
    docs = {d["id"]: d["status"] for d in (await client.get("/me/verification-docs")).json()}
    assert docs[other["id"]] == "pending" and docs[iec["id"]] == "pending"
    assert sorted(docs.values()).count("approved") == 2  # GSTIN + PAN
    [row] = (await admin_client.get("/admin/verify/queue")).json()
    assert row["reviewKind"] == "documents"  # the rest still need a look

    # Revoke flagging the Other entry: its own name comes back as the label.
    r = await admin_client.post(
        f"/admin/users/{body['userId']}/reject",
        json={"reason": "Spices Board number is invalid", "failedItems": [f"doc:{other['id']}"]},
    )
    assert r.status_code == 200
    v = (await client.get("/me")).json()["verification"]
    assert v["rejectedItems"] == [f"doc:{other['id']}"] and v["rejectedItemLabels"] == ["Spices Board registration"]


async def test_approve_approves_the_documents_too(client, admin_client):
    body = await _submitted(client, admin_client, verify=True)
    docs = (await client.get("/me/verification-docs")).json()
    assert {d["status"] for d in docs} == {"approved"}
    assert (await admin_client.get("/admin/verify/queue")).json() == []
    me = (await client.get("/me")).json()
    assert me["status"] == "verified" and me["verification"]["rejectedItems"] == []
    assert body


async def test_verified_business_goes_back_to_review_on_kyb_changes(client, admin_client):
    await _submitted(client, admin_client, verify=True)
    t = await _types(client)

    # An optional document: stays verified, but shows up in the queue for a look.
    r = await client.post("/me/verification-docs", data={"documentTypeId": t["iec"]["id"], "value": "AAACS1234K"})
    assert r.status_code == 201
    assert (await client.get("/me")).json()["status"] == "verified"
    [row] = (await admin_client.get("/admin/verify/queue")).json()
    assert row["reviewKind"] == "documents" and row["status"] == "verified"

    # Non-KYB detail: no change of status.
    r = await client.put(
        "/me/business-profile",
        json={"legalName": "Acme Agro 1 Pvt Ltd", "country": "IN", "addressLine": "1 Market Road", "city": "Karnal", "state": "Haryana"},
    )
    assert r.json()["status"] == "verified"
    # City changed → back to review.
    r = await client.put(
        "/me/business-profile",
        json={"legalName": "Acme Agro 1 Pvt Ltd", "country": "IN", "addressLine": "1 Market Road", "city": "Panipat"},
    )
    assert r.json()["status"] == "pending_verification"
    [row] = (await admin_client.get("/admin/verify/queue")).json()
    assert row["reviewKind"] == "submitted"


async def test_changing_a_required_document_reopens_review(client, admin_client):
    await _submitted(client, admin_client, verify=True)
    gstin = next(d for d in (await client.get("/me/verification-docs")).json() if d["documentTypeCode"] == "gstin")
    r = await client.patch(f"/me/verification-docs/{gstin['id']}", data={"value": "02AAAAA0002A1Z5"})
    assert r.status_code == 200
    assert (await client.get("/me")).json()["status"] == "pending_verification"


# ── countries table ──────────────────────────────────────────────────


async def test_country_details_pause_and_new_country(client, make_client, admin_client):
    doc = {"code": "reg", "name": "Business registration", "inputKind": "file", "isMandatory": True}
    # Known country: details come from the reference; unknown (to the reference) needs a name.
    r = await admin_client.post("/admin/kyb/countries", json={"country": "KE", "documents": [doc]})
    assert r.status_code == 400 and "name" in r.json()["detail"]
    r = await admin_client.post(
        "/admin/kyb/countries",
        json={"country": "KE", "name": "Kenya", "flag": "🇰🇪", "dialCode": "+254", "postalLabel": "Postal code",
              "postalPattern": "[0-9]{5}", "documents": [doc]},
    )
    assert r.status_code == 201, r.text
    assert (await admin_client.post("/admin/kyb/countries", json={"country": "OM", "dialCode": "968", "documents": [doc]})).status_code == 422

    listed = {c["code"]: c for c in (await admin_client.get("/admin/kyb/countries")).json()}
    assert listed["KE"]["name"] == "Kenya" and listed["KE"]["requiredDocuments"] == 1 and listed["KE"]["active"]
    assert listed["IN"]["requiredDocuments"] == 2

    # A business picks Kenya; postcode follows Kenya's pattern; currency default stays per user.
    await signup_and_login(client, "k@nairobigrain.co.ke")
    body = {"legalName": "Nairobi Grain Ltd", "country": "KE", "addressLine": "1 Moi Ave", "city": "Nairobi"}
    assert (await client.put("/me/business-profile", json=body | {"pincode": "12"})).status_code == 400
    r = await client.put("/me/business-profile", json=body | {"pincode": "00100"})
    assert r.status_code == 200 and r.json()["business"]["country"] == "KE"

    # Pause Kenya: new businesses can't pick it; the existing one keeps working.
    r = await admin_client.patch("/admin/kyb/countries/KE", json={"active": False})
    assert r.status_code == 200 and r.json()["active"] is False and r.json()["businesses"] == 1
    assert "KE" not in [c["code"] for c in (await client.get("/kyb/countries")).json()]
    other = make_client()
    await signup_and_login(other, "x@mombasatrade.co.ke")
    r = await other.put("/me/business-profile", json=body | {"legalName": "Mombasa Trade Ltd"})
    assert r.status_code == 400
    r = await client.put("/me/business-profile", json=body | {"pincode": "00100", "state": "Nairobi County"})
    assert r.status_code == 200  # same country, still allowed

    # Edits are audited; names stay unique.
    assert (await admin_client.patch("/admin/kyb/countries/KE", json={"name": "India"})).status_code == 409
    assert (await admin_client.patch("/admin/kyb/countries/KE", json={"active": True, "regionLabel": "County"})).status_code == 200
    async with SessionLocal() as db:
        actions = [a.action for a in await db.scalars(select(AdminAction).order_by(AdminAction.created_at))]
    assert actions.count("kyb_country.create") == 1 and actions.count("kyb_country.update") == 2


async def test_new_users_take_the_country_currency(client):
    await signup_and_login(client, "cur@kaverifoods.in")
    assert (await client.get("/me")).json()["displayCurrency"] == "INR"  # business defaults to IN


async def test_countries_are_referenced_not_free_text():
    import pytest
    from sqlalchemy.exc import IntegrityError

    from app.models.business import Business

    async with SessionLocal() as db:
        db.add(Business(country="ZZ"))
        with pytest.raises(IntegrityError):
            await db.commit()
