"""CSRF Origin guard: state-changing requests from other websites are
refused; our frontend, and non-browser clients, pass."""
from __future__ import annotations

from conftest import signup_and_login

EVIL = "https://evil.example"
OURS = "http://localhost:3000"  # CORS_ORIGINS / FRONTEND_BASE_URL in conftest


async def test_cross_site_post_with_cookie_is_blocked(client):
    await signup_and_login(client, "csrf-owner@kaverifoods.in")
    # e.g. a hidden form on another site trying to log the user out everywhere
    r = await client.post("/auth/logout-all", headers={"Origin": EVIL})
    assert r.status_code == 403
    assert r.json()["detail"] == "Cross-site request blocked."
    # the session survived
    assert (await client.get("/me")).status_code == 200


async def test_our_frontend_origin_passes(client):
    await signup_and_login(client, "csrf-ours@kaverifoods.in")
    r = await client.post("/me/submit-verification", headers={"Origin": OURS})
    assert r.status_code != 403  # reaches the endpoint (400: fields missing)


async def test_referer_used_when_origin_missing(client):
    r = await client.post("/auth/logout", headers={"Referer": f"{EVIL}/attack.html"})
    assert r.status_code == 403
    r = await client.post("/auth/logout", headers={"Referer": f"{OURS}/dashboard"})
    assert r.status_code == 200


async def test_null_origin_blocked(client):
    r = await client.post("/auth/logout", headers={"Origin": "null"})
    assert r.status_code == 403


async def test_non_browser_clients_and_safe_methods_pass(client):
    # no Origin/Referer → curl / server-to-server; can't carry a victim's cookie
    assert (await client.post("/auth/logout")).status_code == 200
    # GET is never blocked, even cross-site
    assert (await client.get("/health", headers={"Origin": EVIL})).status_code == 200


async def test_localhost_only_trusted_in_debug(client):
    # conftest runs with DEBUG=false: other localhost ports are NOT trusted
    r = await client.post("/auth/logout", headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 403
