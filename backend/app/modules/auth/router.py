"""/auth/* — thin HTTP layer over :mod:`app.modules.auth.service`.

    POST /auth/signup/code      work email → 6-digit code emailed
    POST /auth/signup/verify    email + code → email proven
    POST /auth/signup/complete  name, position, password, terms → business +
                                owner created, session cookie issued
    POST /auth/login            email + password → session cookie
    POST /auth/change-password  rotate password (revokes other sessions)
    POST /auth/logout           clear this browser's cookie
    POST /auth/logout-all       revoke every session of the user
    GET  /auth/session          {"userId": …|null}
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app.core.config import settings
from app.core.security import clear_session_cookie, set_session_cookie
from app.models.user import User
from app.modules.auth import service
from app.modules.auth.deps import CurrentUser, DbSession, OptionalUser
from app.modules.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    OkResponse,
    SessionInfo,
    SignupCodeRequest,
    SignupCodeResponse,
    SignupCompleteRequest,
    SignupVerifyRequest,
    SignupVerifyResponse,
)
from app.ratelimit import RateLimitRule, get_limiter, ip_rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])

# Production budgets; multiplied by RATE_LIMIT_DEBUG_MULTIPLIER in debug.
# Per-email code limits (60s cooldown, 5/hour) are DB-backed in the service.
LOGIN_PER_EMAIL = RateLimitRule("auth.login:email", limit=10, window_sec=15 * 60)
LOGIN_PER_IP = RateLimitRule("auth.login:ip", limit=50, window_sec=15 * 60)
SIGNUP_CODE_PER_IP = RateLimitRule("auth.signup_code:ip", limit=20, window_sec=60 * 60)
SIGNUP_VERIFY_PER_IP = RateLimitRule("auth.signup_verify:ip", limit=30, window_sec=15 * 60)
SIGNUP_COMPLETE_PER_IP = RateLimitRule("auth.signup_complete:ip", limit=20, window_sec=60 * 60)


def login_response(user: User) -> LoginResponse:
    return LoginResponse(
        user_id=str(user.id),
        business_id=str(user.business_id),
        role=user.role.value,
        email=user.email,
        business_name=user.business.legal_name,
    )


@router.post(
    "/signup/code",
    response_model=SignupCodeResponse,
    response_model_by_alias=True,
    dependencies=[Depends(ip_rate_limit(SIGNUP_CODE_PER_IP))],
)
async def signup_code(payload: SignupCodeRequest, db: DbSession) -> SignupCodeResponse:
    code = await service.request_signup_code(db, email=payload.email)
    return SignupCodeResponse(
        email=service.normalize_email(payload.email),
        resend_in_sec=int(service.RESEND_COOLDOWN.total_seconds()),
        expires_in_sec=int(service.CODE_TTL.total_seconds()),
        dev_code=code if settings.debug else None,
    )


@router.post(
    "/signup/verify",
    response_model=SignupVerifyResponse,
    response_model_by_alias=True,
    dependencies=[Depends(ip_rate_limit(SIGNUP_VERIFY_PER_IP))],
)
async def signup_verify(payload: SignupVerifyRequest, db: DbSession) -> SignupVerifyResponse:
    await service.verify_signup_code(db, email=payload.email, code=payload.code)
    return SignupVerifyResponse(email=service.normalize_email(payload.email))


@router.post(
    "/signup/complete",
    response_model=LoginResponse,
    response_model_by_alias=True,
    status_code=201,
    dependencies=[Depends(ip_rate_limit(SIGNUP_COMPLETE_PER_IP))],
)
async def signup_complete(payload: SignupCompleteRequest, response: Response, db: DbSession) -> LoginResponse:
    user = await service.complete_signup(
        db,
        email=payload.email,
        full_name=payload.full_name,
        position=payload.position,
        country=payload.country,
        password=payload.password,
    )
    set_session_cookie(response, user.id, user.session_version)
    return login_response(user)


@router.post(
    "/login",
    response_model=LoginResponse,
    response_model_by_alias=True,
    dependencies=[Depends(ip_rate_limit(LOGIN_PER_IP))],
)
async def login(payload: LoginRequest, response: Response, db: DbSession) -> LoginResponse:
    await get_limiter().check(LOGIN_PER_EMAIL, service.normalize_email(payload.email))
    user = await service.authenticate(db, email=payload.email, password=payload.password)
    set_session_cookie(response, user.id, user.session_version)
    return login_response(user)


@router.post("/change-password", response_model=OkResponse, response_model_by_alias=True)
async def change_password(
    payload: ChangePasswordRequest, user: CurrentUser, response: Response, db: DbSession
) -> OkResponse:
    user = await service.change_password(
        db, user, current_password=payload.current_password, new_password=payload.new_password
    )
    # Other sessions are now revoked; keep this browser signed in.
    set_session_cookie(response, user.id, user.session_version)
    return OkResponse()


@router.post("/logout", response_model=OkResponse, response_model_by_alias=True)
async def logout(response: Response) -> OkResponse:
    clear_session_cookie(response)
    return OkResponse()


@router.post("/logout-all", response_model=OkResponse, response_model_by_alias=True)
async def logout_all(user: CurrentUser, response: Response, db: DbSession) -> OkResponse:
    await service.revoke_all_sessions(db, user)
    clear_session_cookie(response)
    return OkResponse()


@router.get("/session", response_model=SessionInfo, response_model_by_alias=True)
async def whoami(user: OptionalUser) -> SessionInfo:
    return SessionInfo(user_id=str(user.id) if user else None)
