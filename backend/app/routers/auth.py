"""Email-only signup + temporary-password login.

Flow:

    POST /auth/signup     { email, firstName, lastName, countryOfResidence }
        creates User (password_hash=NULL), generates a 12-char URL-safe
        random temp password, hashes it into ``temp_credentials``, emails
        the user both the typed password and a magic-login link.

    POST /auth/signup/resend  { email }
        issues a fresh temp credential, invalidating the previous one.

    POST /auth/login      { email, password }
        accepts EITHER a real password OR the temp credential. On
        temp-credential success, flips ``user.must_change_password``
        and drops a session cookie.

    GET  /auth/magic?token=…
        signed-token one-click login — same effect as POST /auth/login
        with the temp password, but no typing. Redirects to
        /dashboard/settings/password.

    POST /auth/logout
    GET  /auth/session
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.email_module import EmailRejection, assert_work_email, send_email
from app.models.profile import Profile
from app.models.temp_credential import TempCredential
from app.models.user import User, UserStatus
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    ResendSignupRequest,
    SignupRequest,
    SignupResponse,
)
from app.user_session import (
    SESSION_COOKIE,
    clear_session_cookie,
    decode_session,
    decode_verify_token,
    issue_verify_token,
    set_session_cookie,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# ─── Tunables ────────────────────────────────────────────────────────

# 12 URL-safe characters: ~71 bits of entropy. Fits on one line in an
# email, still painful to brute-force with the 5-attempt cap below.
_TEMP_PW_BYTES = 9  # token_urlsafe(9) → 12 chars

# Window the typed password works for. 24h is long enough that someone
# checking mail the next morning still succeeds; short enough that an
# abandoned signup doesn't leave a live credential forever.
_TEMP_PW_TTL = timedelta(hours=24)

# Hard cap on wrong-password tries against a single credential. On
# exhaustion the row is marked consumed so the next attempt gets a
# clean "expired, request a new one" response.
_MAX_ATTEMPTS = 5


# ─── Helpers ─────────────────────────────────────────────────────────


def _hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def _frontend_base() -> str:
    base = settings.cors_origin_list[0] if settings.cors_origin_list else "http://localhost:3000"
    return base.rstrip("/")


def _magic_url(token: str) -> str:
    # Backend endpoint, not a frontend route — the backend sets the
    # session cookie and then redirects into the app.
    base = settings.cors_origin_list[0] if settings.cors_origin_list else "http://localhost:3000"
    # Prefer the backend's own origin for the magic link. In dev we only
    # know the frontend origin via CORS, so we rely on the frontend's
    # /api proxy to forward /api/auth/magic to the backend.
    return f"{base.rstrip('/')}/api/auth/magic?token={token}"


# ─── Email templates ────────────────────────────────────────────────


def _welcome_email(*, first_name: str, email: str, temp_password: str, magic_url: str) -> tuple[str, str, str]:
    """Return (subject, html, text) for the welcome-with-temp-password mail."""
    subject = "Welcome to Cor1x — your temporary password"
    text = (
        f"Hi {first_name},\n"
        "\n"
        "Welcome to Cor1x — India's direct-trade agri marketplace.\n"
        "\n"
        "To get started, log in with your temporary password:\n"
        "\n"
        f"  Email:    {email}\n"
        f"  Password: {temp_password}\n"
        "\n"
        "Or click this link to log in with one click:\n"
        f"  {magic_url}\n"
        "\n"
        "This password is valid for 24 hours. The first thing you'll be\n"
        "asked to do inside Cor1x is set a real password of your own.\n"
        "\n"
        "If you didn't sign up for Cor1x, you can ignore this message —\n"
        "the account will stay inert until someone logs in.\n"
        "\n"
        "-- Cor1x\n"
    )
    html = (
        f"<p>Hi {first_name},</p>"
        "<p>Welcome to <strong>Cor1x</strong> — India's direct-trade agri marketplace.</p>"
        "<p>To get started, log in with your temporary password:</p>"
        '<table cellpadding="8" style="border-collapse:collapse;border:1px solid #e5e5e5;">'
        f"<tr><td><strong>Email</strong></td><td><code>{email}</code></td></tr>"
        f"<tr><td><strong>Password</strong></td><td><code>{temp_password}</code></td></tr>"
        "</table>"
        f'<p><a href="{magic_url}" style="display:inline-block;padding:10px 18px;'
        'background:#CEE94A;color:#0b0b0b;text-decoration:none;border-radius:8px;'
        'font-weight:600;">Log me in</a></p>'
        "<p style=\"color:#666;font-size:12px;\">This password is valid for 24 hours. "
        "The first thing you'll be asked to do inside Cor1x is set a real password of "
        "your own.</p>"
        "<p style=\"color:#666;font-size:12px;\">If you didn't sign up for Cor1x, you "
        "can ignore this message — the account will stay inert until someone logs in.</p>"
    )
    return subject, html, text


# ─── Core: temp credential issue ────────────────────────────────────


async def _issue_temp_credential(db: AsyncSession, user: User) -> str:
    """Replace any outstanding credential with a fresh one; return the
    plaintext password (the only time it exists outside bcrypt)."""
    password = secrets.token_urlsafe(_TEMP_PW_BYTES)

    existing = await db.scalar(
        select(TempCredential).where(TempCredential.user_id == user.id)
    )
    now = datetime.now(tz=timezone.utc)
    expires = now + _TEMP_PW_TTL
    if existing is None:
        db.add(
            TempCredential(
                user_id=user.id,
                password_hash=_hash_password(password),
                expires_at=expires,
                attempt_count=0,
                consumed_at=None,
            )
        )
    else:
        existing.password_hash = _hash_password(password)
        existing.expires_at = expires
        existing.attempt_count = 0
        existing.consumed_at = None
    return password


# ─── Signup ──────────────────────────────────────────────────────────


@router.post("/signup", response_model=SignupResponse, response_model_by_alias=True, status_code=201)
async def signup(payload: SignupRequest, db: AsyncSession = Depends(get_db)) -> SignupResponse:
    email = payload.email.strip().lower()
    first_name = payload.first_name.strip()
    last_name = payload.last_name.strip()
    country = payload.country_of_residence.strip()

    try:
        assert_work_email(email)
    except EmailRejection as e:
        raise HTTPException(status_code=400, detail=e.reason) from e

    existing = await db.scalar(select(User).where(User.email == email))
    if existing is not None and existing.deleted_at is None:
        # Account exists AND the owner has already set a real password —
        # that's a straight-up duplicate. Nudge them to log in.
        if existing.password_hash is not None:
            raise HTTPException(
                status_code=409,
                detail="An account with this email already exists. Please log in.",
            )
        # Account exists but still only has a temp credential — treat
        # the second signup as a resend (person probably retyped the
        # form). Overwrite the identity fields so a typo on first try
        # can be corrected.
        user = existing
        profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
        if profile is None:
            profile = Profile(
                user_id=user.id,
                full_name=f"{first_name} {last_name}",
                country=country,
            )
            db.add(profile)
        else:
            profile.full_name = f"{first_name} {last_name}"
            profile.country = country
    else:
        user = User(email=email, password_hash=None, status=UserStatus.signed_up)
        db.add(user)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            raise HTTPException(
                status_code=409,
                detail="An account with this email already exists.",
            )
        db.add(
            Profile(
                user_id=user.id,
                full_name=f"{first_name} {last_name}",
                country=country,
            )
        )
        await db.flush()

    temp_password = await _issue_temp_credential(db, user)
    await db.commit()

    magic = _magic_url(issue_verify_token(str(user.id)))
    subject, html, text = _welcome_email(
        first_name=first_name,
        email=user.email,
        temp_password=temp_password,
        magic_url=magic,
    )
    try:
        send_email(to=user.email, subject=subject, html=html, text=text)
    except Exception as e:
        # Don't leave a half-committed account behind if mail fails —
        # the user has no way in otherwise. Signup can be retried.
        raise HTTPException(
            status_code=502,
            detail=f"Couldn't send your welcome email: {e}. Please try again.",
        ) from e

    return SignupResponse(
        email=user.email,
        dev_temp_password=temp_password if settings.debug else None,
        dev_magic_url=magic if settings.debug else None,
    )


@router.post(
    "/signup/resend",
    response_model=SignupResponse,
    response_model_by_alias=True,
)
async def signup_resend(
    payload: ResendSignupRequest, db: AsyncSession = Depends(get_db)
) -> SignupResponse:
    """Issue a fresh temp password for a signed-up-but-never-logged-in user."""
    email = payload.email.strip().lower()
    user = await db.scalar(select(User).where(User.email == email))
    if user is None or user.deleted_at is not None:
        # Don't leak which emails exist — same shape as a success.
        return SignupResponse(email=email)
    if user.password_hash is not None:
        raise HTTPException(
            status_code=409,
            detail="This account already has a password set — please log in instead.",
        )

    profile = await db.scalar(select(Profile).where(Profile.user_id == user.id))
    first_name = (profile.full_name.split()[0] if profile and profile.full_name else "there")

    temp_password = await _issue_temp_credential(db, user)
    await db.commit()

    magic = _magic_url(issue_verify_token(str(user.id)))
    subject, html, text = _welcome_email(
        first_name=first_name,
        email=user.email,
        temp_password=temp_password,
        magic_url=magic,
    )
    try:
        send_email(to=user.email, subject=subject, html=html, text=text)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Mail delivery failed: {e}") from e

    return SignupResponse(
        email=user.email,
        dev_temp_password=temp_password if settings.debug else None,
        dev_magic_url=magic if settings.debug else None,
    )


# ─── Login ───────────────────────────────────────────────────────────


async def _try_temp_credential(
    db: AsyncSession, user: User, password: str
) -> bool:
    """Verify ``password`` against the user's temp credential, with the
    full defensive dance (expiry, consumed, attempt cap). Returns True
    on success and marks the credential consumed.
    """
    cred = await db.scalar(
        select(TempCredential).where(TempCredential.user_id == user.id)
    )
    if cred is None or cred.consumed_at is not None:
        return False
    now = datetime.now(tz=timezone.utc)
    if cred.expires_at < now:
        return False
    if cred.attempt_count >= _MAX_ATTEMPTS:
        # Burn the credential — forces a resend before any more tries
        # can land.
        cred.consumed_at = now
        return False
    ok = _verify_password(password, cred.password_hash)
    if not ok:
        cred.attempt_count += 1
        return False
    cred.consumed_at = now
    return True


@router.post("/login", response_model=LoginResponse, response_model_by_alias=True)
async def login(
    payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> LoginResponse:
    email = payload.email.strip().lower()
    user = await db.scalar(select(User).where(User.email == email))
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    # Try the real password first (fast path for logged-in users).
    real_ok = (
        user.password_hash is not None
        and _verify_password(payload.password, user.password_hash)
    )
    temp_ok = False
    if not real_ok:
        temp_ok = await _try_temp_credential(db, user, payload.password)
        await db.commit()
        if not temp_ok:
            raise HTTPException(status_code=401, detail="Invalid email or password.")

    # Mark the account email-verified on first login — receiving the
    # password proves inbox ownership. (Older users whose stamp is
    # already set are left alone.)
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(tz=timezone.utc)
    if user.status == UserStatus.signed_up:
        user.status = UserStatus.email_verified

    if temp_ok:
        user.must_change_password = True
    await db.commit()

    set_session_cookie(response, str(user.id))
    return LoginResponse(
        user_id=str(user.id),
        email=user.email,
        business_name=user.business_name,
        must_change_password=user.must_change_password,
    )


# ─── Magic link ──────────────────────────────────────────────────────


@router.get("/magic")
async def magic_login(token: str, db: AsyncSession = Depends(get_db)) -> RedirectResponse:
    """Shortcut from the welcome email that drops the user on /login
    with their email pre-filled.

    The link does NOT drop a session on its own — the user still types
    the temp password on the login screen. This keeps the credential
    flow single-track (one place where a session gets issued) and
    means a magic URL leaked from a mail archive on its own can't log
    anyone in. All it does is remove the "wait, which account was
    this?" friction when someone clicks after a day away.
    """
    uid = decode_verify_token(token)
    frontend_base = _frontend_base()
    if not uid:
        return RedirectResponse(
            url=f"{frontend_base}/login?magic=invalid", status_code=303
        )
    user = await db.scalar(select(User).where(User.id == uid))
    if user is None or user.deleted_at is not None:
        return RedirectResponse(
            url=f"{frontend_base}/login?magic=invalid", status_code=303
        )

    # Stamp email_verified_at on first click — receiving the link
    # proves inbox ownership even if the user types the password manually.
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(tz=timezone.utc)
    if user.status == UserStatus.signed_up:
        user.status = UserStatus.email_verified
    await db.commit()

    from urllib.parse import quote

    return RedirectResponse(
        url=f"{frontend_base}/login?email={quote(user.email)}&from=magic",
        status_code=303,
    )


# ─── Change password ─────────────────────────────────────────────────


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    cor1x_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    """Set a password for the account.

    Two modes:

    * **First-time setup** — ``user.must_change_password == True``.
      The session cookie was just issued via temp-password login (or
      magic link), so inbox ownership is already proven. We don't
      re-check the temp password here — it's typically been consumed
      by the login that just happened. The caller may still send
      ``current_password`` for UX consistency; it's ignored.
    * **Rotation** — the user already has a real password set and is
      changing it. ``current_password`` must match
      ``user.password_hash`` exactly, same as any standard change-pw
      screen.
    """
    uid = decode_session(cor1x_session) if cor1x_session else None
    if not uid:
        raise HTTPException(status_code=401, detail="Not signed in.")
    user = await db.scalar(select(User).where(User.id == uid))
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=401, detail="Not signed in.")

    first_time = user.must_change_password or user.password_hash is None
    if not first_time:
        if not _verify_password(payload.current_password, user.password_hash or ""):
            raise HTTPException(
                status_code=401, detail="Current password is incorrect."
            )
        if payload.new_password == payload.current_password:
            raise HTTPException(
                status_code=400,
                detail="New password must be different from the current one.",
            )

    user.password_hash = _hash_password(payload.new_password)
    user.must_change_password = False

    # Clear the temp credential row — it's served its purpose and
    # leaving it around would just be extra attack surface.
    cred = await db.scalar(
        select(TempCredential).where(TempCredential.user_id == user.id)
    )
    if cred is not None:
        await db.delete(cred)

    await db.commit()
    return {"ok": True}


# ─── Session utilities ───────────────────────────────────────────────


@router.post("/logout")
async def logout(response: Response) -> dict[str, bool]:
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/session")
async def whoami(
    cor1x_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
) -> dict[str, str | None]:
    uid = decode_session(cor1x_session) if cor1x_session else None
    return {"userId": uid}
