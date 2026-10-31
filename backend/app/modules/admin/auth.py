"""/admin/login, /admin/logout, /admin/me, /admin/change-password."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response

from app.core.security import ADMIN_COOKIE, clear_cookie, set_cookie
from app.models.admin_user import AdminUser
from app.modules.admin import accounts
from app.modules.admin.deps import SignedInAdmin, ensure_ip_allowed
from app.modules.admin.permissions import permissions_for
from app.modules.admin.schemas import AdminChangePasswordIn, LoginIn, LoginOut
from app.modules.auth import sessions
from app.modules.auth.deps import DbSession
from app.ratelimit import RateLimitRule, get_limiter, ip_rate_limit

router = APIRouter()

ADMIN_LOGIN_PER_IP = RateLimitRule("admin.login:ip", limit=10, window_sec=15 * 60)
ADMIN_LOGIN_PER_EMAIL = RateLimitRule("admin.login:email", limit=10, window_sec=15 * 60)


def _out(a: AdminUser) -> LoginOut:
    return LoginOut(
        id=str(a.id), email=a.email, full_name=a.full_name, role=a.role.value,
        permissions=sorted(p.value for p in permissions_for(a.role)), must_change_password=a.must_change_password,
    )


@router.post(
    "/login",
    response_model=LoginOut,
    response_model_by_alias=True,
    dependencies=[Depends(ip_rate_limit(ADMIN_LOGIN_PER_IP))],
)
async def admin_login(
    payload: LoginIn, request: Request, response: Response, db: DbSession, client: sessions.Client
) -> LoginOut:
    ensure_ip_allowed(request)
    await get_limiter().check(ADMIN_LOGIN_PER_EMAIL, payload.email.strip().lower())
    admin = await accounts.authenticate(db, email=payload.email, password=payload.password, client=client)
    policy = sessions.admin_policy()
    token, _ = await sessions.start_session(db, policy, admin.id, client)
    set_cookie(response, ADMIN_COOKIE, token, sessions.cookie_max_age(policy))
    return _out(admin)


@router.post("/logout")
async def admin_logout(
    response: Response,
    db: DbSession,
    client: sessions.Client,
    cor1x_admin: Annotated[str | None, Cookie(alias=ADMIN_COOKIE)] = None,
) -> dict[str, bool]:
    await sessions.end_session(db, sessions.admin_policy(), cor1x_admin, client)
    clear_cookie(response, ADMIN_COOKIE)
    return {"ok": True}


@router.get("/me", response_model=LoginOut, response_model_by_alias=True)
async def admin_me(admin: SignedInAdmin, db: DbSession) -> LoginOut:
    return _out(await db.get(AdminUser, admin.id))


@router.post("/change-password", response_model=LoginOut, response_model_by_alias=True)
async def admin_change_password(
    payload: AdminChangePasswordIn, admin: SignedInAdmin, db: DbSession, client: sessions.Client
) -> LoginOut:
    row = await accounts.change_own_password(
        db, admin.id, current=payload.current_password, new=payload.new_password,
        keep_session=admin.session_id, client=client,
    )
    return _out(row)
