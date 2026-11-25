"""/auth/* — thin HTTP layer over :mod:`app.modules.auth.service`.

    POST /auth/signup/code      work email → 6-digit code emailed
    POST /auth/signup/verify    email + code → email proven
    POST /auth/signup/complete  name, position, password, terms → business +
                                owner created, session cookie issued
    POST /auth/login            email + password → session cookie (signs
                                out any other device; lockout after 5 fails;
                                emails the user on a browser not seen before)
    POST /auth/change-password  rotate password (revokes other sessions;
                                emails the user)
    POST /auth/password/forgot  email → reset code (same answer either way)
    POST /auth/password/reset   email + code + new password → all sessions out
    POST /auth/logout           end this browser's session
    POST /auth/logout-all       revoke every session of the user
    GET  /auth/session          {"userId": …|null}
    GET  /auth/security         signed-in device + recent sign-in activity
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import notifications
from app.core.config import settings
from app.core.errors import NotFound
from app.core.security import SESSION_COOKIE, clear_cookie, parse_uuid, set_cookie
from app.core.time import utcnow
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
from app.modules.masking import service as masking
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
    "sessions_revoked", "session_signed_out", "password_changed", "password_reset",
)


async def login_response(db: AsyncSession, user: User) -> LoginResponse:
    identity = await masking.own_identity(db, user.business_id)
    person = await masking.own_person(db, user.id)
    return LoginResponse(
        user_id=str(user.id),
        business_id=str(user.business_id),
        role=user.role.value,
        email=person.email,
        business_name=identity.legal_name,
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
        country=payload.country,
        position=payload.position,
        password=payload.password,
    )
    sessions.record_event(db, subject_type="user", subject_id=user.id, event="login_succeeded", client=client)
    await _start(db, response, user, client)
    return await login_response(db, user)


@router.post(
    "/login",
    response_model=LoginResponse,
    response_model_by_alias=True,
    dependencies=[Depends(ip_rate_limit(LOGIN_PER_IP))],
)
async def login(
    payload: LoginRequest,
    response: Response,
    db: DbSession,
    client: sessions.Client,
    background: BackgroundTasks,
    cor1x_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> LoginResponse:
    await get_limiter().check(LOGIN_PER_EMAIL, service.normalize_email(payload.email))
    signin = await service.authenticate(db, email=payload.email, password=payload.password, client=client)
    user = signin.user
    # Signing in again in the same browser replaces its session instead of
    # taking a second of the five places.
    await sessions.end_session(db, sessions.user_policy(), cor1x_session, client)
    await _start(db, response, user, client)
    if signin.new_device:
        person = await masking.own_person(db, user.id)
        background.add_task(
            notifications.deliver_safely,
            notifications.send_new_device_signin,
            to=person.email,
            first_name=notifications.first_name_of(person.full_name),
            device=sessions.device_label(client.user_agent),
            signed_in_at=utcnow(),
        )
    return await login_response(db, user)


@router.post("/change-password", response_model=OkResponse, response_model_by_alias=True)
async def change_password(
    payload: ChangePasswordRequest, user: CurrentUser, session_id: CurrentSessionId, db: DbSession,
    client: sessions.Client, background: BackgroundTasks,
) -> OkResponse:
    # Other sessions are revoked; this browser stays signed in.
    await service.change_password(
        db, user, current_password=payload.current_password, new_password=payload.new_password,
        keep_session=session_id, client=client,
    )
    await _notify_password_changed(db, background, user)
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
async def reset_password(
    payload: ResetPasswordRequest, response: Response, db: DbSession, client: sessions.Client,
    background: BackgroundTasks,
) -> OkResponse:
    user = await service.reset_password(
        db, email=payload.email, code=payload.code, new_password=payload.new_password, client=client
    )
    await _notify_password_changed(db, background, user)
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


def _device(row, current_id) -> DeviceOut:
    return DeviceOut(
        id=str(row.id), created_at=row.created_at, last_seen_at=row.last_seen_at, expires_at=row.expires_at,
        ip_prefix=row.ip_prefix, user_agent=row.user_agent, current=row.id == current_id,
    )


@router.get("/security", response_model=SecurityOverview, response_model_by_alias=True)
async def security_overview(user: CurrentUser, session_id: CurrentSessionId, db: DbSession) -> SecurityOverview:
    policy = sessions.user_policy()
    live = await sessions.live_sessions(db, policy, user.id)
    devices = [_device(row, session_id) for row in live]
    events = await db.scalars(
        select(AuthEvent)
        .where(AuthEvent.subject_type == "user", AuthEvent.subject_id == user.id, AuthEvent.event.in_(VISIBLE_EVENTS))
        .order_by(AuthEvent.created_at.desc())
        .limit(20)
    )
    return SecurityOverview(
        device=next((d for d in devices if d.current), None),
        devices=devices,
        max_devices=policy.max_active,
        recent=[AuthEventOut.model_validate(e, from_attributes=True) for e in events],
        idle_timeout_minutes=int(policy.idle.total_seconds() // 60),
        max_session_days=policy.absolute.days,
    )


@router.delete("/sessions/{session_id}", status_code=204, response_class=Response, response_model=None)
async def sign_out_device(
    session_id: str, user: CurrentUser, current: CurrentSessionId, db: DbSession, client: sessions.Client
) -> Response:
    """Sign one of your other devices out. This device signs out with /logout."""
    target = parse_uuid(session_id)
    if target is None or target == current:
        raise NotFound("No such device is signed in.")
    if not await sessions.revoke_one(db, sessions.user_policy(), user.id, target, client):
        raise NotFound("No such device is signed in.")
    return Response(status_code=204)


async def _notify_password_changed(db: DbSession, background: BackgroundTasks, user: User) -> None:
    """Tell the account holder, so a change they didn't make is noticed."""
    person = await masking.own_person(db, user.id)
    background.add_task(
        notifications.deliver_safely,
        notifications.send_password_changed,
        to=person.email,
        first_name=notifications.first_name_of(person.full_name),
        changed_at=utcnow(),
    )


async def _start(db: DbSession, response: Response, user: User, client: sessions.ClientInfo) -> None:
    """Commit the login changes, start a session, set the cookie."""
    policy = sessions.user_policy()
    token, _ = await sessions.start_session(db, policy, user.id, client)
    set_cookie(response, SESSION_COOKIE, token, sessions.cookie_max_age(policy))
