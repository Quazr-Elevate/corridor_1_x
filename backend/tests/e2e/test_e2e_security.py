"""E2E-SEC — the promises we make about other people's data.

Tenancy (business A can never touch business B), what the anonymous market
is allowed to show, private KYB files, upload sniffing, CSRF, rate limits
and error shapes. Scenario IDs match ``docs/testing/SCENARIOS.md``.
"""
from __future__ import annotations

from flows import (
    PDF_BYTES,
    list_lot,
    photo,
    product_body,
    sign_up,
    verified_trader,
)


# ── One business can never reach another's data ──────────────────────


async def test_e2e_sec_100_businesses_are_isolated(make_client, admin_client, counter):
    """E2E-SEC-100: A's ids are useless in B's hands — lots, KYB entries,
    files and numbers all stay with their owner."""
    a = await verified_trader(make_client, admin_client, counter, prefix="sec100a")
    b = await verified_trader(make_client, admin_client, counter, prefix="sec100b")
    a_lot = await list_lot(a)
    a_entry = (await a.client.get("/me/verification-docs")).json()[0]

    # B's own views only ever show B's things.
    assert (await b.client.get("/products")).json() == []
    b_entries = (await b.client.get("/me/verification-docs")).json()
    assert a_entry["id"] not in [e["id"] for e in b_entries]

    # B can't delete A's lot, read A's KYB entry, open its file or reveal it.
    assert (await b.client.delete(f"/products/{a_lot['id']}")).status_code == 404
    assert (await b.client.get(f"/me/verification-docs/{a_entry['id']}/file")).status_code == 404
    assert (await b.client.post(f"/me/verification-docs/{a_entry['id']}/reveal")).status_code == 404
    assert (await b.client.delete(f"/me/verification-docs/{a_entry['id']}")).status_code == 404
    assert (
        await b.client.patch(f"/me/verification-docs/{a_entry['id']}", data={"value": "33AAAAA9999A1Z5"})
    ).status_code == 404


async def test_e2e_sec_110_kyb_files_are_never_public(make_client, admin_client, counter):
    """E2E-SEC-110: a KYB document has no public URL, and the owner's own
    download is marked no-store."""
    t = await verified_trader(make_client, admin_client, counter, prefix="sec110")
    r = await t.client.post(
        "/me/verification-docs",
        data={"customName": "Organic certificate"},
        files={"file": ("organic.pdf", PDF_BYTES, "application/pdf")},
    )
    assert r.status_code == 201, r.text
    entry = r.json()
    assert entry["url"] == f"/me/verification-docs/{entry['id']}/file"

    own = await t.client.get(entry["url"])
    assert own.status_code == 200
    assert own.headers["cache-control"] == "private, no-store"
    assert own.headers["x-content-type-options"] == "nosniff"

    # Anonymous: nothing, by any route.
    anon = make_client()
    assert (await anon.get(entry["url"])).status_code == 401
    assert (await anon.get(f"/admin/docs/{entry['id']}/file")).status_code == 401
    assert (await anon.get(f"/uploads/products/{entry['id']}.pdf")).status_code == 404


async def test_e2e_sec_120_the_public_market_leaks_no_contact_details(make_client, admin_client, counter):
    """E2E-SEC-120: until a reveal happens, nothing identifying the seller is
    in any public response."""
    seller = await verified_trader(make_client, admin_client, counter, prefix="sec120")
    lot = await list_lot(seller)

    anon = make_client()
    bodies = [
        (await anon.get("/public/products")).text,
        (await anon.get(f"/public/products/{lot['id']}")).text,
        (await anon.get("/public/catalog/facets")).text,
    ]
    for body in bodies:
        assert seller.email not in body
        assert "Asha Rao" not in body
        assert "Market Road" not in body  # the registered address
        assert f"Acme Agro {seller.n} Pvt Ltd" not in body
        assert "AAAAA" not in body  # PAN / GSTIN shapes


async def test_e2e_sec_130_product_photos_are_served_safely(make_client, counter):
    """E2E-SEC-130: uploads are sniffed, not trusted; the served file has a
    correct type, nosniff, and path traversal is impossible."""
    t = await sign_up(make_client, counter, prefix="sec130")

    # A lie about the content type doesn't help.
    r = await t.client.post("/products/upload-photo", files={"file": ("x.png", b"<html>evil</html>", "image/png")})
    assert r.status_code == 415
    r = await t.client.post("/products/upload-photo", files={"file": ("x.png", PDF_BYTES, "image/png")})
    assert r.status_code == 415, "a PDF is not a product photo"

    url = await photo(t)
    anon = make_client()
    served = await anon.get(url)
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"
    assert served.headers["x-content-type-options"] == "nosniff"
    assert served.headers["content-disposition"] == "inline"

    for path in ("/uploads/products/../../cor1x.db", "/uploads/products/nothere.png"):
        assert (await anon.get(path)).status_code == 404


async def test_e2e_sec_140_a_lot_can_only_use_photos_that_were_uploaded(make_client, counter):
    """E2E-SEC-140: the photo list is validated — no remote URLs, no made-up
    local paths."""
    t = await sign_up(make_client, counter, prefix="sec140")
    for photos in (
        [],
        ["https://evil.example/x.png"],
        ["/uploads/products/" + "a" * 32 + ".png"],
        ["/etc/passwd"],
    ):
        r = await t.client.post("/products", json=product_body(photos))
        assert r.status_code == 400, f"{photos} → {r.status_code}"


# ── CSRF ─────────────────────────────────────────────────────────────


async def test_e2e_sec_200_a_foreign_origin_cannot_write(make_client, counter):
    """E2E-SEC-200: a cross-site form post with a stolen cookie is refused on
    every unsafe method."""
    t = await sign_up(make_client, counter, prefix="sec200")
    evil = {"Origin": "https://evil.example"}

    assert (await t.client.post("/me/submit-verification", headers=evil)).status_code == 403
    assert (await t.client.patch("/me", json={"displayCurrency": "USD"}, headers=evil)).status_code == 403
    assert (await t.client.post("/auth/logout", headers=evil)).status_code == 403
    assert (await t.client.delete("/me", headers=evil)).status_code == 403

    # Reads are fine, and the real frontend origin is accepted.
    assert (await t.client.get("/me", headers=evil)).status_code == 200
    r = await t.client.patch("/me", json={"displayCurrency": "USD"}, headers={"Origin": "http://localhost:3000"})
    assert r.status_code == 200


async def test_e2e_sec_210_the_admin_console_is_csrf_protected_too(admin_client):
    """E2E-SEC-210: the same guard covers /admin writes."""
    r = await admin_client.post("/admin/logout", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert (await admin_client.get("/admin/me")).status_code == 200, "still signed in"


# ── Rate limits ──────────────────────────────────────────────────────


async def test_e2e_sec_300_signup_codes_have_a_cooldown(make_client):
    """E2E-SEC-300: hammering "resend code" is throttled, with Retry-After so
    the UI can count down."""
    from flows import email_for

    c = make_client()
    email = email_for("sec300")
    assert (await c.post("/auth/signup/code", json={"email": email})).status_code == 200

    again = await c.post("/auth/signup/code", json={"email": email})
    assert again.status_code == 429, again.text
    assert int(again.headers["retry-after"]) > 0


async def test_e2e_sec_310_revealing_your_own_numbers_is_capped(make_client, admin_client, counter):
    """E2E-SEC-310: the reveal endpoint can't be used to dump data in a loop."""
    t = await verified_trader(make_client, admin_client, counter, prefix="sec310")
    entry = (await t.client.get("/me/verification-docs")).json()[0]

    statuses = set()
    for _ in range(31):
        statuses.add((await t.client.post(f"/me/verification-docs/{entry['id']}/reveal")).status_code)
    assert 200 in statuses and 429 in statuses


# ── Plumbing ─────────────────────────────────────────────────────────


async def test_e2e_sec_400_errors_have_one_shape(make_client, counter):
    """E2E-SEC-400: failures are ``{"detail": …}`` with a request id, and
    never leak a stack trace."""
    t = await sign_up(make_client, counter, prefix="sec400")

    missing = await t.client.get("/public/products/00000000-0000-4000-8000-000000000000")
    assert missing.status_code == 404
    assert set(missing.json()) == {"detail"} and isinstance(missing.json()["detail"], str)
    assert missing.headers.get("x-request-id")

    bad = await t.client.post("/products", json={"name": "x"})
    assert bad.status_code == 422 and "detail" in bad.json()

    for body in (missing.text, bad.text):
        assert "Traceback" not in body and "sqlalchemy" not in body.lower()


async def test_e2e_sec_410_private_responses_are_not_cached(make_client, counter):
    """E2E-SEC-410: signed-in responses carry no-store and the usual security
    headers (an intermediary must not keep them)."""
    t = await sign_up(make_client, counter, prefix="sec410")
    r = await t.client.get("/me")
    assert r.status_code == 200
    assert "no-store" in r.headers.get("cache-control", "")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-request-id")


async def test_e2e_sec_420_health_is_public_and_honest(make_client):
    """E2E-SEC-420: the health check the platform polls needs no session."""
    r = await make_client().get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"
