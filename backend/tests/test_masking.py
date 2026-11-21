"""The identity vault (CX-079 … CX-083): company codes, the response guard,
audited staff access, erasure, and the rule that only ``modules/masking``
touches the vault."""
from __future__ import annotations

import re
import typing
import uuid
from pathlib import Path

from conftest import fill_mandatory, set_status, signup_and_login
from fastapi.routing import APIRoute, iter_route_contexts
from pydantic import BaseModel
from sqlalchemy import select
from test_admin_accounts import _new_admin

from app.core.db import SessionLocal
from app.main import app
from app.models import VAULT_COLUMNS, AdminAction, Business, BusinessIdentity, BusinessStatus
from app.modules.masking import service as masking
from app.ratelimit import get_limiter

APP_DIR = Path(__file__).resolve().parent.parent / "app"

# ── Response guard (CX-082) ──────────────────────────────────────────

#: Field names that carry a company's or a person's identity, or the
#: internal id that stands in for one. A response model outside /admin may
#: only contain them on a route listed below.
IDENTITY_FIELDS = frozenset(VAULT_COLUMNS) | {
    "business_name", "full_name", "email", "phone", "seller_id", "business_id", "user_id",
}

OWN = "the caller's own account and company"
#: (method, path) → why this route may answer with identity fields.
ALLOWED = {
    ("POST", "/auth/signup/code"): "echoes the email the caller typed",
    ("POST", "/auth/signup/verify"): "echoes the email the caller typed",
    ("POST", "/auth/signup/complete"): OWN,
    ("POST", "/auth/login"): OWN,
    ("GET", "/auth/session"): OWN,
    ("GET", "/me"): OWN,
    ("PATCH", "/me"): OWN,
    ("PUT", "/me/business-profile"): OWN,
    ("GET", "/pincode/{pincode}"): "postal reference data: the city of a PIN code, not of a company",
    ("GET", "/ifsc/{code}"): "bank branch reference data",
    # Off by default (A-030) and deleted with the reveal code (CX-083).
    ("POST", "/products/{product_id}/contact-reveal"): "retired contact reveal, refused unless the setting is on",
}

#: Routes with no JSON body: empty answers and files.
NO_BODY = {
    ("GET", "/health"),
    ("DELETE", "/me"),
    ("DELETE", "/me/business/{slot}"),
    ("DELETE", "/me/verification-docs/{doc_id}"),
    ("GET", "/me/verification-docs/{doc_id}/file"),
    ("DELETE", "/products/{product_id}"),
    ("DELETE", "/rfqs/{rfq_id}"),
    ("DELETE", "/products/{product_id}/certificates/{certificate_id}"),
    ("GET", "/products/{product_id}/certificates/{certificate_id}/file"),
    ("GET", "/uploads/products/{filename}"),
    ("GET", "/uploads/branding/{filename}"),
}


def _external_routes():
    for ctx in iter_route_contexts(app.routes):
        route = ctx.original_route
        path = ctx.path.removeprefix("/v1")
        if isinstance(route, APIRoute) and not path.startswith("/admin"):
            for method in ctx.methods:
                yield (method, path), route


def _identity_fields(annotation, seen: set, prefix: str = "") -> list[str]:
    """Every identity field reachable from a response annotation."""
    found: list[str] = []
    for arg in typing.get_args(annotation):
        found += _identity_fields(arg, seen, prefix)
    if isinstance(annotation, type) and issubclass(annotation, BaseModel) and annotation not in seen:
        seen.add(annotation)
        for name, field in annotation.model_fields.items():
            if name in IDENTITY_FIELDS:
                found.append(prefix + name)
            found += _identity_fields(field.annotation, seen, f"{prefix}{name}.")
    return found


def test_no_external_response_can_carry_an_identity_field():
    routes = dict(_external_routes())
    assert len(routes) > 40, "Too few routes found; the guard would pass on nothing."
    leaks, unmodelled = [], []
    for key, route in routes.items():
        if route.response_model is None:
            if key not in NO_BODY:
                unmodelled.append(f"{key[0]} {key[1]}")
            continue
        fields = _identity_fields(route.response_model, set())
        if fields and key not in ALLOWED:
            leaks.append(f"{key[0]} {key[1]}: {', '.join(fields)}")
    assert not leaks, "Identity fields in an external response:\n" + "\n".join(leaks)
    assert not unmodelled, "External routes without a response model:\n" + "\n".join(unmodelled)
    # An exception that no longer applies must be removed, not left to rot.
    stale = [k for k in ALLOWED if k not in routes or not _identity_fields(routes[k].response_model, set())]
    assert not stale, f"ALLOWED entries that no longer need to be there: {stale}"
    assert not [k for k in NO_BODY if k not in routes], "NO_BODY names a route that is gone."


def test_the_guard_sees_nested_and_listed_fields():
    class Inner(BaseModel):
        legal_name: str

    class Outer(BaseModel):
        rows: list[Inner]
        seller: Inner | None = None

    assert _identity_fields(Outer, set()) == ["rows.legal_name"]
    assert _identity_fields(list[Outer] | None, set()) == ["rows.legal_name"]


def test_only_the_masking_module_reads_the_vault():
    """``BusinessIdentity`` may be named for typing anywhere, but only
    ``modules/masking`` may query, create or delete it."""
    query = re.compile(r"(select|delete|update|insert)\(\s*BusinessIdentity|db\.get\(\s*BusinessIdentity|BusinessIdentity\(")
    allowed = ("modules/masking/", "models/business_identity.py")  # the door, and the table itself
    offenders = [
        str(path.relative_to(APP_DIR))
        for path in APP_DIR.rglob("*.py")
        if not any(a in path.as_posix() for a in allowed) and query.search(path.read_text())
    ]
    assert offenders == []


# ── Company codes (CX-080) ───────────────────────────────────────────


def test_codes_are_country_plus_six_random_digits():
    codes = {masking.new_code("in") for _ in range(200)}
    assert all(re.fullmatch(r"IN-\d{6}", c) for c in codes)
    assert len(codes) > 190  # random, not a counter
    assert masking.new_code("AE").startswith("AE-")


async def test_a_code_is_issued_at_verification_and_kept_for_life(client, admin_client):
    me = await signup_and_login(client, "owner@kaverifoods.in")
    await fill_mandatory(client)
    assert (await client.get("/me")).json()["companyCode"] is None
    assert (await client.post("/me/submit-verification")).status_code == 200
    assert (await admin_client.post(f"/admin/users/{me['userId']}/verify")).status_code == 200
    code = (await client.get("/me")).json()["companyCode"]
    assert re.fullmatch(r"IN-\d{6}", code)

    # A profile change sends the business back to review; approving it again
    # must not hand out a second code.
    r = await client.put("/me/business-profile", json={"legalName": "Kaveri Foods Renamed", "country": "IN", "city": "Pune"})
    assert r.status_code == 200, r.text
    await set_status(me["userId"], BusinessStatus.pending_verification)
    assert (await admin_client.post(f"/admin/users/{me['userId']}/verify")).status_code == 200
    assert (await client.get("/me")).json()["companyCode"] == code


async def test_assign_code_retries_past_a_taken_code(monkeypatch):
    async with SessionLocal() as db:
        first = Business(id=uuid.uuid4(), country="IN", company_code="IN-000001")
        second = Business(id=uuid.uuid4(), country="IN")
        db.add_all([first, second])
        await db.flush()
        offered = iter(["IN-000001", "IN-000001", "IN-000002"])
        monkeypatch.setattr(masking, "new_code", lambda _country: next(offered))
        assert await masking.assign_code(db, second) == "IN-000002"
        assert await masking.assign_code(db, first) == "IN-000001"  # unchanged


# ── Staff access (CX-081) ────────────────────────────────────────────


async def _unmask_rows() -> list[AdminAction]:
    async with SessionLocal() as db:
        return list(
            await db.scalars(
                select(AdminAction)
                .where(AdminAction.action.like("identity.%"), AdminAction.action != "identity.listed")
                .order_by(AdminAction.created_at)
            )
        )


async def test_opening_an_account_writes_identity_unmasked(client, admin_client):
    me = await signup_and_login(client, "owner@kaverifoods.in", company_name="Kaveri Foods Pvt Ltd")
    # A page of the directory shows names and is not an unmask.
    listed = (await admin_client.get("/admin/users")).json()["items"]
    assert listed[0]["businessName"] == "Kaveri Foods Pvt Ltd"
    assert await _unmask_rows() == []
    # ...but the page leaves a trace of how many names it showed (C21).
    async with SessionLocal() as db:
        (page,) = list(await db.scalars(select(AdminAction).where(AdminAction.action == "identity.listed")))
    assert (page.target_type, page.details) == ("admin_user", {"purpose": "directory", "count": 1})
    assert "Kaveri" not in str(page.details)

    # Opening the account needs a reason (C22), and the old GET is gone.
    assert (await admin_client.post(f"/admin/users/{me['userId']}/open", json={})).status_code == 422
    assert (await admin_client.get(f"/admin/users/{me['userId']}")).status_code == 405
    assert await _unmask_rows() == []
    detail = await admin_client.post(f"/admin/users/{me['userId']}/open", json={"reason": "KYB review of this business"})
    assert detail.status_code == 200 and detail.json()["businessProfile"]["legalName"] == "Kaveri Foods Pvt Ltd"
    (row,) = await _unmask_rows()
    assert (row.action, row.target_type, row.target_id) == ("identity.unmasked", "business", me["businessId"])
    assert row.details == {"purpose": "account_detail", "company_code": None}
    assert row.reason == "KYB review of this business"
    assert "Kaveri" not in str(row.details)  # the log says who was opened, never the name


async def test_unmask_by_code_needs_the_permission_and_a_reason(client, admin_client, make_client):
    me = await signup_and_login(client, "owner@kaverifoods.in", company_name="Kaveri Foods Pvt Ltd")
    await set_status(me["userId"], BusinessStatus.verified)
    code = (await client.get("/me")).json()["companyCode"]
    url = f"/admin/companies/{code}/unmask"

    assert (await make_client().post(url, json={"reason": "Buyer dispute on a deal"})).status_code == 401
    _, reviewer = await _new_admin(admin_client, make_client)
    assert (await reviewer.post(url, json={"reason": "Buyer dispute on a deal"})).status_code == 403
    assert (await client.post(url, json={"reason": "I am a trader"})).status_code == 401
    assert (await admin_client.post(url, json={})).status_code == 422
    assert (await admin_client.post(url, json={"reason": "abc"})).status_code == 422
    assert (await admin_client.post("/admin/companies/IN-999999/unmask", json={"reason": "Wrong code"})).status_code == 404
    assert await _unmask_rows() == []

    r = await admin_client.post(f"/admin/companies/{code.lower()}/unmask", json={"reason": "Buyer dispute on a deal"})
    assert r.status_code == 200, r.text
    assert r.json()["legalName"] == "Kaveri Foods Pvt Ltd" and r.json()["companyCode"] == code
    (row,) = await _unmask_rows()
    assert row.reason == "Buyer dispute on a deal"
    assert row.details == {"purpose": "code_lookup", "company_code": code}


async def test_unmask_volume_is_flagged_once_then_stopped(client, admin_client, monkeypatch):
    me = await signup_and_login(client, "owner@kaverifoods.in")
    limiter = get_limiter()
    monkeypatch.setattr(limiter, "multiplier", 1)
    monkeypatch.setattr(masking, "STAFF_UNMASK_ALERT", masking.RateLimitRule("identity.unmask_alert:admin", 3, 3600))
    monkeypatch.setattr(masking, "STAFF_UNMASK", masking.RateLimitRule("identity.unmask:admin", 6, 3600))

    for _ in range(6):
        assert (await admin_client.post(f"/admin/users/{me['userId']}/open", json={"reason": "KYB review of this business"})).status_code == 200
    blocked = await admin_client.post(f"/admin/users/{me['userId']}/open", json={"reason": "KYB review of this business"})
    assert blocked.status_code == 429 and "retry-after" in blocked.headers

    actions = [r.action for r in await _unmask_rows()]
    assert actions.count("identity.unmasked") == 6
    assert actions.count("identity.bulk_access") == 1  # one alert, not one per view
    assert actions.index("identity.bulk_access") == 4  # raised on the fourth view


# ── Erasure ──────────────────────────────────────────────────────────


async def test_deleting_the_account_erases_the_vault_row_and_frees_the_name(client, make_client):
    me = await signup_and_login(client, "owner@kaverifoods.in", company_name="Kaveri Foods Pvt Ltd")
    taken = make_client()
    await signup_and_login(taken, "second@othermill.in")
    r = await taken.put("/me/business-profile", json={"legalName": "kaveri foods pvt ltd", "country": "IN"})
    assert r.status_code == 409

    assert (await client.delete("/me")).status_code == 204
    async with SessionLocal() as db:
        assert await db.get(BusinessIdentity, uuid.UUID(me["businessId"])) is None
        assert (await db.get(Business, uuid.UUID(me["businessId"]))).deleted_at is not None
    r = await taken.put("/me/business-profile", json={"legalName": "Kaveri Foods Pvt Ltd", "country": "IN"})
    assert r.status_code == 200, r.text
