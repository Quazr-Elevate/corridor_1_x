"""E2E-KYB — the Passport and its documents, across countries.

Corridor onboards India and the UAE with different required documents, and
ops can change that list from the console. These journeys check that a
trader is always asked for the right things, that changing KYB data after
approval sends the business back to review, and that validation holds.
Scenario IDs match ``docs/testing/SCENARIOS.md``.
"""
from __future__ import annotations

from flows import PDF_BYTES, admin_verify, sign_up, submit


async def _types(c, country: str | None = None) -> dict[str, dict]:
    path = "/kyb/document-types" + (f"?country={country}" if country else "")
    return {t["code"]: t for t in (await c.get(path)).json()}


# ── Choosing a country ───────────────────────────────────────────────


async def test_e2e_kyb_100_only_countries_corridor_onboards_are_offered(make_client, counter):
    """E2E-KYB-100: the country picker is the list ops set up, and anything
    else is refused with a readable reason."""
    t = await sign_up(make_client, counter, prefix="kyb100")
    countries = (await t.client.get("/kyb/countries")).json()
    assert [c["code"] for c in countries] == ["IN", "AE"]

    india = [c for c in countries if c["code"] == "IN"][0]
    assert india["defaultCurrency"] == "INR" and india["postalLabel"] == "PIN code"

    r = await t.client.put(
        "/me/business-profile",
        json={"legalName": "Kaveri Foods Pvt Ltd", "country": "SA", "addressLine": "1 Road", "city": "Riyadh"},
    )
    assert r.status_code == 400 and "onboard" in r.json()["detail"]


async def test_e2e_kyb_110_a_uae_business_is_asked_for_uae_documents(make_client, admin_client, counter):
    """E2E-KYB-110: the whole journey for a Dubai trader — a trade licence
    (file), not a GSTIN."""
    t = await sign_up(make_client, counter, prefix="kyb110", domain="gulfgrain.ae")
    r = await t.client.put(
        "/me/business-profile",
        json={
            "legalName": f"Gulf Grain Trading LLC {t.n}",
            "country": "AE",
            "addressLine": "Office 12, Al Ras",
            "city": "Dubai",
        },
    )
    assert r.status_code == 200, r.text

    types = await _types(t.client)
    assert "trade_licence" in types and "gstin" not in types
    assert types["trade_licence"]["inputKind"] == "file"

    state = (await t.client.get("/me")).json()["verification"]
    assert "kyb:trade_licence" in state["missing"]

    # A number alone doesn't satisfy a file-only document.
    r = await t.client.post(
        "/me/verification-docs", data={"documentTypeId": types["trade_licence"]["id"], "value": "12345"}
    )
    assert r.status_code == 400, r.text

    r = await t.client.post(
        "/me/verification-docs",
        data={"documentTypeId": types["trade_licence"]["id"]},
        files={"file": ("licence.pdf", PDF_BYTES, "application/pdf")},
    )
    assert r.status_code == 201, r.text

    await t.client.post("/onboarding/contact", json={"fullName": "Omar Hassan", "phone": f"+971 50 000 {t.n:04d}"})
    await t.client.post("/onboarding/business", json={"tradePosition": "buyer"})
    r = await t.client.post(
        "/onboarding/company",
        json={
            "legalName": f"Gulf Grain Trading LLC {t.n}",
            "industry": "Rice",
            "operatingCountries": ["AE", "IN"],
            "addressLine": "Office 12, Al Ras",
            "city": "Dubai",
            "country": "AE",
        },
    )
    assert r.status_code == 200, r.text

    me = (await t.client.get("/me")).json()
    assert me["verification"]["missing"] == [], me["verification"]["missing"]
    # Display currency is chosen at signup (before a country is picked), so a
    # UAE business starts on the signup default and switches it itself.
    assert me["displayCurrency"] == "INR"
    assert (await t.client.patch("/me", json={"displayCurrency": "AED"})).json()["displayCurrency"] == "AED"

    await submit(t)
    await admin_verify(admin_client, t)
    assert (await t.client.get("/me")).json()["status"] == "verified"


# ── Document validation ──────────────────────────────────────────────


async def test_e2e_kyb_200_numbers_must_match_their_pattern(make_client, counter):
    """E2E-KYB-200: a malformed GSTIN or PAN is refused at entry, so ops
    never review junk."""
    t = await sign_up(make_client, counter, prefix="kyb200")
    await t.client.put(
        "/me/business-profile",
        json={"legalName": f"Pattern Foods {t.n}", "country": "IN", "addressLine": "1 Road", "city": "Karnal"},
    )
    types = await _types(t.client)

    for code, bad in (("gstin", "NOT-A-GSTIN"), ("pan", "123"), ("gstin", "")):
        r = await t.client.post("/me/verification-docs", data={"documentTypeId": types[code]["id"], "value": bad})
        assert r.status_code == 400, f"{code}={bad!r} → {r.status_code}"

    r = await t.client.post(
        "/me/verification-docs", data={"documentTypeId": types["gstin"]["id"], "value": "22AAAAA0000A1Z5"}
    )
    assert r.status_code == 201, r.text
    # The list never carries the full number.
    entry = r.json()
    assert entry["valueMasked"] and "22AAAAA0000A1Z5" not in str(entry)
    revealed = await t.client.post(f"/me/verification-docs/{entry['id']}/reveal")
    assert revealed.json()["value"] == "22AAAAA0000A1Z5"


async def test_e2e_kyb_210_one_entry_per_document_type(make_client, counter):
    """E2E-KYB-210: a type is added once; a second attempt is a conflict and
    the fix is to edit the existing entry."""
    t = await sign_up(make_client, counter, prefix="kyb210")
    await t.client.put(
        "/me/business-profile",
        json={"legalName": f"Once Foods {t.n}", "country": "IN", "addressLine": "1 Road", "city": "Karnal"},
    )
    types = await _types(t.client)
    first = await t.client.post(
        "/me/verification-docs", data={"documentTypeId": types["pan"]["id"], "value": "AAAAA1111A"}
    )
    assert first.status_code == 201

    second = await t.client.post(
        "/me/verification-docs", data={"documentTypeId": types["pan"]["id"], "value": "AAAAA2222A"}
    )
    assert second.status_code == 409, second.text

    updated = await t.client.patch(
        f"/me/verification-docs/{first.json()['id']}", data={"value": "AAAAA2222A"}
    )
    assert updated.status_code == 200
    assert (await t.client.post(f"/me/verification-docs/{first.json()['id']}/reveal")).json()["value"] == "AAAAA2222A"


async def test_e2e_kyb_220_oversized_and_unknown_files_are_refused(make_client, counter):
    """E2E-KYB-220: KYB uploads are sniffed and size-capped."""
    t = await sign_up(make_client, counter, prefix="kyb220")
    r = await t.client.post(
        "/me/verification-docs",
        data={"customName": "Random file"},
        files={"file": ("notes.txt", b"just text, not a document", "application/pdf")},
    )
    assert r.status_code == 415, r.text

    r = await t.client.post(
        "/me/verification-docs",
        data={"customName": "Huge scan"},
        files={"file": ("big.pdf", PDF_BYTES + b"0" * (12 * 1024 * 1024), "application/pdf")},
    )
    assert r.status_code in (400, 413), r.text


async def test_e2e_kyb_230_an_other_entry_can_be_named_and_removed(make_client, counter):
    """E2E-KYB-230: extra certificates go in as "Other" with a free-text name
    and can be deleted again."""
    t = await sign_up(make_client, counter, prefix="kyb230")
    r = await t.client.post(
        "/me/verification-docs",
        data={"customName": "Organic certificate"},
        files={"file": ("organic.pdf", PDF_BYTES, "application/pdf")},
    )
    assert r.status_code == 201, r.text
    entry = r.json()
    assert entry["isOther"] is True and entry["certType"] == "Organic certificate"

    assert (await t.client.delete(f"/me/verification-docs/{entry['id']}")).status_code == 204
    assert entry["id"] not in [e["id"] for e in (await t.client.get("/me/verification-docs")).json()]
    assert (await t.client.get(f"/me/verification-docs/{entry['id']}/file")).status_code == 404


# ── Changing KYB data after approval ─────────────────────────────────


async def test_e2e_kyb_300_editing_kyb_data_sends_a_verified_business_back(make_client, admin_client, counter):
    """E2E-KYB-300: a verified company changes its registered address — it
    goes back to review automatically and its lots leave the market."""
    from flows import fill_passport, list_lot

    t = await sign_up(make_client, counter, prefix="kyb300")
    await fill_passport(t)
    await submit(t)
    await admin_verify(admin_client, t)
    await list_lot(t)

    anon = make_client()
    assert (await anon.get("/public/products")).json()["total"] == 1

    r = await t.client.put(
        "/me/business-profile",
        json={
            "legalName": f"Acme Agro {t.n} Pvt Ltd",
            "country": "IN",
            "addressLine": "99 Different Road",
            "city": "Karnal",
        },
    )
    assert r.status_code == 200, r.text
    assert (await t.client.get("/me")).json()["status"] == "pending_verification"
    assert (await anon.get("/public/products")).json()["total"] == 0

    await admin_verify(admin_client, t)
    assert (await anon.get("/public/products")).json()["total"] == 1


async def test_e2e_kyb_310_contact_changes_do_not_reopen_review(make_client, admin_client, counter):
    """E2E-KYB-310: who to call is not KYB data — editing it leaves a verified
    business verified."""
    from flows import fill_passport

    t = await sign_up(make_client, counter, prefix="kyb310")
    await fill_passport(t)
    await submit(t)
    await admin_verify(admin_client, t)

    r = await t.client.post(
        "/onboarding/contact", json={"fullName": "Asha Rao", "phone": f"+91 98765 1111{t.n}", "position": "CEO"}
    )
    assert r.status_code == 200, r.text
    assert (await t.client.get("/me")).json()["status"] == "verified"


async def test_e2e_kyb_320_ops_adding_a_required_document_reopens_review(make_client, admin_client, counter):
    """E2E-KYB-320: ops makes another Indian document mandatory — verified
    businesses that lack it are asked for it."""
    from flows import fill_passport

    t = await sign_up(make_client, counter, prefix="kyb320")
    await fill_passport(t)
    await submit(t)
    await admin_verify(admin_client, t)

    admin_types = {t_["code"]: t_ for t_ in (await admin_client.get("/admin/kyb/document-types?country=IN")).json()}
    r = await admin_client.patch(f"/admin/kyb/document-types/{admin_types['iec']['id']}", json={"isMandatory": True})
    assert r.status_code == 200, r.text

    state = (await t.client.get("/me")).json()["verification"]
    assert "kyb:iec" in state["missing"]
    assert state["mandatoryTotal"] >= 5

    # Supplying it closes the gap again.
    types = await _types(t.client)
    r = await t.client.post(
        "/me/verification-docs", data={"documentTypeId": types["iec"]["id"], "value": "AAAAA0000B"}
    )
    assert r.status_code == 201, r.text
    assert (await t.client.get("/me")).json()["verification"]["missing"] == []
