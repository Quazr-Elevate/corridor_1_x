"""/auth/* — thin HTTP layer over :mod:`app.modules.auth.service`.

    POST /auth/signup/code      work email → 6-digit code emailed
    POST /auth/signup/verify    email + code → email proven
    POST /auth/signup/complete  name, position, password, terms → business +
                                owner created, session cookie issued
    POST /auth/login            email + password → session cookie (signs
                                out any other device; lockout after 5 fails)
    POST /auth/change-password  rotate password (revokes other sessions)
    POST /auth/password/forgot  email → reset code (same answer either way)
    POST /auth/password/reset   email + code + new password → all sessions out
    POST /auth/logout           end this browser's session
    POST /auth/logout-all       revoke every session of the user
    GET  /auth/session          {"userId": …|null}
    GET  /auth/security         signed-in device + recent sign-in activity
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy import select

from app.core.config import settings
from app.core.security import SESSION_COOKIE, clear_cookie, set_cookie
from app.models.auth_session import AuthEvent
from app.models.user import User
from app.modules.auth import service, sessions
from app.modules.auth.deps import CurrentSessionId, CurrentUser, DbSession, OptionalUser
from app.modules.auth.schemas import (
    AuthEventOut,
    ChangePasswordRequest,
    DeviceOut,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LoginResponse,
    OkResponse,
    ResetPasswordRequest,
    SecurityOverview,
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
FORGOT_PER_IP = RateLimitRule("auth.forgot:ip", limit=10, window_sec=60 * 60)
RESET_PER_IP = RateLimitRule("auth.reset:ip", limit=20, window_sec=15 * 60)

#: Events shown to the user on /auth/security.
VISIBLE_EVENTS = (
    "login_succeeded", "login_failed", "locked", "locked_support", "unlocked", "session_replaced",
    "sessions_revoked", "password_changed", "password_reset",
)


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
async def signup_complete(
    payload: SignupCompleteRequest, response: Response, db: DbSession, client: sessions.Client
) -> LoginResponse:
    user = await service.complete_signup(
        db,
        email=payload.email,
        full_name=payload.full_name,
        company_name=payload.company_name,
        position=payload.position,
        password=payload.password,
    )
    sessions.record_event(db, subject_type="user", subject_id=user.id, event="login_succeeded", client=client)
    await _start(db, response, user, client)
    return login_response(user)


@router.post(
    "/login",
    response_model=LoginResponse,
    response_model_by_alias=True,
    dependencies=[Depends(ip_rate_limit(LOGIN_PER_IP))],
)
async def login(payload: LoginRequest, response: Response, db: DbSession, client: sessions.Client) -> LoginResponse:
    await get_limiter().check(LOGIN_PER_EMAIL, service.normalize_email(payload.email))
    user = await service.authenticate(db, email=payload.email, password=payload.password, client=client)
    await _start(db, response, user, client)
    return login_response(user)


@router.post("/change-password", response_model=OkResponse, response_model_by_alias=True)
async def change_password(
    payload: ChangePasswordRequest, user: CurrentUser, session_id: CurrentSessionId, db: DbSession,
    client: sessions.Client,
) -> OkResponse:
    # Other sessions are revoked; this browser stays signed in.
    await service.change_password(
        db, user, current_password=payload.current_password, new_password=payload.new_password,
        keep_session=session_id, client=client,
    )
    return OkResponse()


@router.post(
    "/password/forgot",
    response_model=ForgotPasswordResponse,
    response_model_by_alias=True,
    dependencies=[Depends(ip_rate_limit(FORGOT_PER_IP))],
)
async def forgot_password(payload: ForgotPasswordRequest, db: DbSession, client: sessions.Client) -> ForgotPasswordResponse:
    code = await service.request_password_reset(db, email=payload.email, client=client)
    return ForgotPasswordResponse(
        expires_in_sec=int(service.CODE_TTL.total_seconds()), dev_code=code if settings.debug else None
    )


@router.post(
    "/password/reset",
    response_model=OkResponse,
    response_model_by_alias=True,
    dependencies=[Depends(ip_rate_limit(RESET_PER_IP))],
)
async def reset_password(payload: ResetPasswordRequest, response: Response, db: DbSession, client: sessions.Client) -> OkResponse:
    await service.reset_password(
        db, email=payload.email, code=payload.code, new_password=payload.new_password, client=client
    )
    clear_cookie(response, SESSION_COOKIE)
    return OkResponse()


@router.post("/logout", response_model=OkResponse, response_model_by_alias=True)
async def logout(
    response: Response,
    db: DbSession,
    client: sessions.Client,
    cor1x_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> OkResponse:
    await sessions.end_session(db, sessions.user_policy(), cor1x_session, client)
    clear_cookie(response, SESSION_COOKIE)
    return OkResponse()


@router.post("/logout-all", response_model=OkResponse, response_model_by_alias=True)
async def logout_all(user: CurrentUser, response: Response, db: DbSession, client: sessions.Client) -> OkResponse:
    await service.revoke_all_sessions(db, user, client)
    clear_cookie(response, SESSION_COOKIE)
    return OkResponse()


@router.get("/session", response_model=SessionInfo, response_model_by_alias=True)
async def whoami(user: OptionalUser) -> SessionInfo:
    return SessionInfo(user_id=str(user.id) if user else None)


@router.get("/security", response_model=SecurityOverview, response_model_by_alias=True)
async def security_overview(user: CurrentUser, db: DbSession) -> SecurityOverview:
    policy = sessions.user_policy()
    active = await sessions.active_session(db, policy, user.id)
    events = await db.scalars(
        select(AuthEvent)
        .where(AuthEvent.subject_type == "user", AuthEvent.subject_id == user.id, AuthEvent.event.in_(VISIBLE_EVENTS))
        .order_by(AuthEvent.created_at.desc())
        .limit(20)
    )
    return SecurityOverview(
        device=DeviceOut.model_validate(active, from_attributes=True) if active else None,
        recent=[AuthEventOut.model_validate(e, from_attributes=True) for e in events],
        idle_timeout_minutes=int(policy.idle.total_seconds() // 60),
        max_session_days=policy.absolute.days,
    )


async def _start(db: DbSession, response: Response, user: User, client: sessions.ClientInfo) -> None:
    """Commit the login changes, start the one active session, set the cookie."""
    policy = sessions.user_policy()
    token, _ = await sessions.start_session(db, policy, user.id, client)
    set_cookie(response, SESSION_COOKIE, token, sessions.cookie_max_age(policy))
