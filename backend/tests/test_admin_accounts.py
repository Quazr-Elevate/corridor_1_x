"""Phase A — named admins, roles, the route-permission matrix, admin
sessions, lockout and the IP allowlist."""
from __future__ import annotations

from datetime import timedelta

import pytest
from conftest import ADMIN_EMAIL, ADMIN_PASSWORD
from fastapi.routing import APIRoute
from sqlalchemy import select, update

from app.core.db import SessionLocal
from app.core.time import utcnow
from app.main import app
from app.models.admin_action import AdminAction
from app.models.admin_user import AdminUser
from app.models.auth_session import AdminSession
from app.modules.admin.permissions import REVIEWER

PUBLIC_ADMIN_ROUTES = {("POST", "/admin/login"), ("POST", "/admin/logout")}
NEW_PW = "Reviewer-pass-2026!"


def _admin_routes():
    for r in app.routes:
        if isinstance(r, APIRoute) and r.path.startswith("/admin"):
            for m in r.methods:
                yield m, r.path, r


def _route_permission(route: APIRoute):
    found = []
    for dep in route.dependant.dependencies:
        if hasattr(dep.call, "permission"):
            found.append(dep.call.permission)
    return found


async def _new_admin(admin_client, make_client, role="reviewer", email="rev@cor1x.test"):
    r = await admin_client.post("/admin/admins", json={"email": email, "fullName": "Riya Reviewer", "role": role})
    assert r.status_code == 201, r.text
    body = r.json()
    c = make_client()
    r = await c.post("/admin/login", json={"email": email, "password": body["temporaryPassword"]})
    assert r.status_code == 200 and r.json()["mustChangePassword"] is True
    r = await c.post(
        "/admin/change-password", json={"currentPassword": body["temporaryPassword"], "newPassword": NEW_PW}
    )
    assert r.status_code == 200 and r.json()["mustChangePassword"] is False
    return body["admin"]["id"], c


# ── Route matrix ─────────────────────────────────────────────────────


def test_every_admin_route_declares_exactly_one_permission():
    missing = []
    for method, path, route in _admin_routes():
        if (method, path) in PUBLIC_ADMIN_ROUTES:
            continue
        perms = _route_permission(route)
        if len(perms) != 1:
            missing.append(f"{method} {path}: {perms}")
    assert not missing, "Admin routes without exactly one permission:\n" + "\n".join(missing)


SUPER_ONLY = sorted(
    (m, p) for m, p, r in _admin_routes()
    if (m, p) not in PUBLIC_ADMIN_ROUTES and (perm := _route_permission(r)[0]) is not None and perm not in REVIEWER
)


def test_super_only_routes_are_the_expected_ones():
    paths = {p for _, p in SUPER_ONLY}
    assert "/admin/admins" in paths and "/admin/kyb/countries" in paths and "/admin/users/{user_id}/unlock" in paths
    assert "/admin/verify/queue" not in paths and "/admin/docs/{doc_id}/reveal" not in paths


@pytest.mark.parametrize("method,path", SUPER_ONLY)
async def test_reviewer_is_forbidden_on_super_only_routes(admin_client, make_client, method, path):
    _, rev = await _new_admin(admin_client, make_client)
    url = path.replace("{user_id}", "00000000-0000-0000-0000-000000000000").replace(
        "{admin_id}", "00000000-0000-0000-0000-000000000000").replace("{type_id}", "x").replace("{code}", "IN")
    r = await rev.request(method, url, json={})
    assert r.status_code == 403, (method, path, r.status_code, r.text)


async def test_reviewer_can_review(admin_client, make_client):
    _, rev = await _new_admin(admin_client, make_client)
    assert (await rev.get("/admin/verify/queue")).status_code == 200
    assert (await rev.get("/admin/users")).status_code == 200
    assert (await rev.get("/admin/kyb/document-types")).status_code == 200
    me = (await rev.get("/admin/me")).json()
    assert me["role"] == "reviewer" and "admins.manage" not in me["permissions"]
    assert set(me["permissions"]) == {p.value for p in REVIEWER}


# ── Accounts ─────────────────────────────────────────────────────────


async def test_bootstrap_creates_super_admin_once(make_client):
    c = make_client()
    assert (await c.post("/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})).status_code == 200
    async with SessionLocal() as db:
        rows = list(await db.scalars(select(AdminUser)))
    assert len(rows) == 1 and rows[0].role.value == "super_admin" and rows[0].created_by == "bootstrap"


async def test_temporary_password_gate(admin_client, make_client):
    r = await admin_client.post("/admin/admins", json={"email": "gate@cor1x.test", "fullName": "Gate Keeper", "role": "reviewer"})
    temp = r.json()["temporaryPassword"]
    c = make_client()
    await c.post("/admin/login", json={"email": "gate@cor1x.test", "password": temp})
    assert (await c.get("/admin/verify/queue")).status_code == 403
    assert (await c.get("/admin/me")).status_code == 200
    short = await c.post("/admin/change-password", json={"currentPassword": temp, "newPassword": "short"})
    assert short.status_code == 422


async def test_duplicate_admin_email(admin_client):
    body = {"email": "dup@cor1x.test", "fullName": "Dup Admin", "role": "reviewer"}
    assert (await admin_client.post("/admin/admins", json=body)).status_code == 201
    assert (await admin_client.post("/admin/admins", json=body | {"email": "DUP@cor1x.test"})).status_code == 409


async def test_last_super_admin_and_self_guards(admin_client):
    me = (await admin_client.get("/admin/me")).json()
    r = await admin_client.patch(f"/admin/admins/{me['id']}", json={"role": "reviewer"})
    assert r.status_code == 400
    r = await admin_client.patch(f"/admin/admins/{me['id']}", json={"status": "disabled"})
    assert r.status_code == 400


async def test_disable_admin_ends_session(admin_client, make_client):
    rid, rev = await _new_admin(admin_client, make_client)
    assert (await admin_client.patch(f"/admin/admins/{rid}", json={"status": "disabled"})).status_code == 200
    assert (await rev.get("/admin/me")).status_code == 401
    r = await make_client().post("/admin/login", json={"email": "rev@cor1x.test", "password": NEW_PW})
    assert r.status_code == 401


async def test_reset_password_and_sign_out(admin_client, make_client):
    rid, rev = await _new_admin(admin_client, make_client)
    r = await admin_client.post(f"/admin/admins/{rid}/reset-password")
    assert r.status_code == 200 and r.json()["admin"]["mustChangePassword"] is True
    assert (await rev.get("/admin/me")).status_code == 401
    rid2, rev2 = await _new_admin(admin_client, make_client, email="rev2@cor1x.test")
    assert (await admin_client.post(f"/admin/admins/{rid2}/sign-out")).status_code == 200
    assert (await rev2.get("/admin/me")).status_code == 401


async def test_admin_actions_carry_admin_user_id(admin_client):
    me = (await admin_client.get("/admin/me")).json()
    await admin_client.post("/admin/admins", json={"email": "audit@cor1x.test", "fullName": "Audit Me", "role": "reviewer"})
    async with SessionLocal() as db:
        row = await db.scalar(select(AdminAction).where(AdminAction.action == "admin.create"))
    assert str(row.admin_user_id) == me["id"] and row.admin_email == ADMIN_EMAIL


# ── Sessions / lockout ───────────────────────────────────────────────


async def test_admin_one_device_and_idle_timeout(admin_client, make_client):
    other = make_client()
    assert (await other.post("/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})).status_code == 200
    assert (await admin_client.get("/admin/me")).status_code == 401
    async with SessionLocal() as db:
        await db.execute(
            update(AdminSession).where(AdminSession.revoked_at.is_(None))
            .values(last_seen_at=utcnow() - timedelta(minutes=31))
        )
        await db.commit()
    assert (await other.get("/admin/me")).status_code == 401


async def test_admin_cookie_lifetime(make_client):
    r = await make_client().post("/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert "Max-Age=28800" in r.headers["set-cookie"]


async def test_admin_lockout_and_unlock(admin_client, make_client):
    rid, _ = await _new_admin(admin_client, make_client)
    c = make_client()
    codes = [(await c.post("/admin/login", json={"email": "rev@cor1x.test", "password": "nope"})).status_code for _ in range(5)]
    assert codes == [401, 401, 401, 401, 423]
    rows = {a["id"]: a for a in (await admin_client.get("/admin/admins")).json()}
    assert rows[rid]["lockState"] == "temporary"
    assert (await admin_client.post(f"/admin/admins/{rid}/unlock")).status_code == 200
    assert (await c.post("/admin/login", json={"email": "rev@cor1x.test", "password": NEW_PW})).status_code == 200


async def test_admin_ip_allowlist(admin_client, make_client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "admin_ip_allowlist", "203.0.113.0/24")
    assert (await admin_client.get("/admin/me")).status_code == 403
    r = await make_client().post("/admin/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 403
    monkeypatch.setattr(settings, "admin_ip_allowlist", "127.0.0.1")  # httpx ASGITransport's client address
    assert (await admin_client.get("/admin/me")).status_code == 200


async def test_user_cookie_never_works_on_admin(client):
    from conftest import signup_and_login

    from app.core.security import ADMIN_COOKIE, SESSION_COOKIE

    await signup_and_login(client, "notadmin@kaverifoods.in")
    client.cookies.set(ADMIN_COOKIE, client.cookies.get(SESSION_COOKIE))
    assert (await client.get("/admin/users")).status_code == 401

