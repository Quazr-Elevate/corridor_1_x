"""/admin/login, /admin/logout, /admin/me."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.core.config import settings
from app.core.errors import Unauthorized
from app.core.security import AdminEmail, clear_admin_cookie, set_admin_cookie, verify_admin_credentials
from app.modules.admin.schemas import LoginIn, LoginOut
from app.ratelimit import RateLimitRule, ip_rate_limit

router = APIRouter()

ADMIN_LOGIN_PER_IP = RateLimitRule("admin.login:ip", limit=10, window_sec=15 * 60)


@router.post(
    "/login",
    response_model=LoginOut,
    response_model_by_alias=True,
    dependencies=[Depends(ip_rate_limit(ADMIN_LOGIN_PER_IP))],
)
async def admin_login(payload: LoginIn, response: Response) -> LoginOut:
    if not verify_admin_credentials(payload.email, payload.password):
        raise Unauthorized("Invalid credentials")
    set_admin_cookie(response, settings.admin_email)
    return LoginOut(email=settings.admin_email)


@router.post("/logout")
async def admin_logout(response: Response) -> dict[str, bool]:
    clear_admin_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=LoginOut, response_model_by_alias=True)
async def admin_me(email: AdminEmail) -> LoginOut:
    return LoginOut(email=email)
