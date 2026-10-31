"""Auth business rules: signup with an emailed 6-digit code (send → verify →
complete), login (with lockout), password change and reset, session
revocation. No FastAPI imports.

Signup proves inbox ownership in place: no account row exists until the
code was verified, and the account (business + owner user) is created in
one transaction that consumes the code.
"""
from __future__ import annotations

import functools
import hashlib
import hmac
import logging
import secrets
import uuid
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import notifications
from app.core.config import settings
from app.core.errors import BadRequest, Conflict, Forbidden, TooManyRequests, Unauthorized, UpstreamError
from app.core.security import hash_password, verify_password
from app.core.time import ensure_aware, utcnow
from app.integrations.email import EmailRejection, assert_work_email
from app.models.business import Business, BusinessStatus
from app.models.email_code import EmailCode, EmailCodePurpose
from app.models.user import AccountStatus, User, UserRole
from app.modules.accounts.uniqueness import LEGAL_NAME_TAKEN, ensure_company_available
from app.modules.auth import lockout, sessions
from app.modules.auth.sessions import ClientInfo, record_event

log = logging.getLogger("app.auth")

CODE_DIGITS = 6
CODE_TTL = timedelta(minutes=10)
RESEND_COOLDOWN = timedelta(seconds=60)
CODES_PER_HOUR = 5
MAX_CODE_ATTEMPTS = 5
# After the code is verified the user has this long to finish the form.
VERIFIED_WINDOW = timedelta(minutes=30)

#: Version of the Terms / Privacy Policy accepted at signup (DPDP / PDPL
#: trail). Bump when /terms or /privacy change materially.
TERMS_VERSION = "2026-08-29"

ACCOUNT_EXISTS = "An account with this email already exists. Please log in."


@functools.cache
def _dummy_hash() -> str:
    return hash_password(secrets.token_hex(8))


def normalize_email(raw: str) -> str:
    return raw.strip().lower()


def hash_code(email: str, purpose: EmailCodePurpose, code: str) -> str:
    """HMAC-SHA256 (server secret) of the code, bound to email + purpose."""
    msg = f"{purpose.value}:{email}:{code}".encode()
    return hmac.new(settings.session_secret.encode(), msg, hashlib.sha256).hexdigest()


def _hourly_cap() -> int:
    return CODES_PER_HOUR * (max(1, settings.rate_limit_debug_multiplier) if settings.debug else 1)


async def _latest_code(db: AsyncSession, email: str, purpose: EmailCodePurpose) -> EmailCode | None:
    return await db.scalar(
        select(EmailCode)
        .where(EmailCode.email == email, EmailCode.purpose == purpose)
        .order_by(EmailCode.created_at.desc(), EmailCode.id.desc())
        .limit(1)
    )


async def _email_taken(db: AsyncSession, email: str) -> bool:
    return await db.scalar(select(User.id).where(User.email == email)) is not None


# ── Signup ───────────────────────────────────────────────────────────


async def request_signup_code(db: AsyncSession, *, email: str) -> str:
    """Issue + email a fresh code (older ones for this email stop working).
    Returns the plaintext code (for the DEBUG-only ``devCode``)."""
    email = normalize_email(email)
    try:
        assert_work_email(email)
    except EmailRejection as e:
        raise BadRequest(e.reason) from e
    if await _email_taken(db, email):
        raise Conflict(ACCOUNT_EXISTS)

    purpose = EmailCodePurpose.signup
    now = utcnow()
    latest = await _latest_code(db, email, purpose)
    if latest is not None and ensure_aware(latest.created_at) + RESEND_COOLDOWN > now:
        wait = int((ensure_aware(latest.created_at) + RESEND_COOLDOWN - now).total_seconds()) + 1
        raise TooManyRequests(f"Please wait {wait}s before requesting a new code.", retry_after=wait)
    hour_ago = now - timedelta(hours=1)
    recent = list(
        await db.scalars(
            select(EmailCode.created_at)
            .where(EmailCode.email == email, EmailCode.purpose == purpose, EmailCode.created_at >= hour_ago)
            .order_by(EmailCode.created_at.asc())
        )
    )
    if len(recent) >= _hourly_cap():
        retry = int((ensure_aware(recent[0]) + timedelta(hours=1) - now).total_seconds()) + 1
        raise TooManyRequests(
            "Too many codes requested for this email. Try again later.", retry_after=max(1, retry)
        )

    # Issuing a new code invalidates older unused ones.
    await db.execute(
        update(EmailCode)
        .where(
            EmailCode.email == email,
            EmailCode.purpose == purpose,
            EmailCode.consumed_at.is_(None),
            EmailCode.expires_at > now,
        )
        .values(expires_at=now)
    )
    code = f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"
    db.add(
        EmailCode(
            email=email,
            purpose=purpose,
            code_hash=hash_code(email, purpose, code),
            attempts=0,
            expires_at=now + CODE_TTL,
            created_at=now,
        )
    )
    await db.flush()
    try:
        await notifications.send_signup_code(
            to=email, code=code, valid_minutes=int(CODE_TTL.total_seconds() // 60)
        )
    except Exception as e:
        await db.rollback()
        log.exception("signup_code_email_failed")
        raise UpstreamError("Couldn't send the code email. Please try again.") from e
    await db.commit()
    return code


async def verify_signup_code(db: AsyncSession, *, email: str, code: str) -> None:
    """Mark the latest code verified. 5 wrong tries kill it; it expires
    after 10 minutes."""
    email = normalize_email(email)
    code = "".join(ch for ch in code if ch.isdigit())
    purpose = EmailCodePurpose.signup
    row = await _latest_code(db, email, purpose)
    if row is None or row.consumed_at is not None:
        raise BadRequest("Request a code first.")
    now = utcnow()
    if row.verified_at is not None and hmac.compare_digest(row.code_hash, hash_code(email, purpose, code)):
        return  # idempotent re-submit of the right code
    if row.attempts >= MAX_CODE_ATTEMPTS:
        raise BadRequest("Too many wrong attempts. Request a new code.")
    if ensure_aware(row.expires_at) <= now:
        raise BadRequest("This code has expired. Request a new one.")
    if not hmac.compare_digest(row.code_hash, hash_code(email, purpose, code)):
        row.attempts += 1
        left = MAX_CODE_ATTEMPTS - row.attempts
        await db.commit()
        if left <= 0:
            raise BadRequest("Too many wrong attempts. Request a new code.")
        raise BadRequest(f"That code isn't right. {left} attempt{'s' if left != 1 else ''} left.")
    row.verified_at = now
    await db.commit()


async def complete_signup(
    db: AsyncSession,
    *,
    email: str,
    full_name: str,
    company_name: str,
    position: str | None,
    password: str,
) -> User:
    """One transaction: business (draft, named) + owner user + code consumed.
    Country defaults to IN until set on the business profile."""
    email = normalize_email(email)
    if await _email_taken(db, email):
        raise Conflict(ACCOUNT_EXISTS)
    company_name = " ".join(company_name.split())
    await ensure_company_available(db, uuid.uuid4(), legal_name=company_name)
    row = await _latest_code(db, email, EmailCodePurpose.signup)
    if row is None or row.verified_at is None:
        raise BadRequest("Verify your email first.")
    if row.consumed_at is not None:
        raise BadRequest("This code was already used. Request a new one.")
    now = utcnow()
    if ensure_aware(row.verified_at) + VERIFIED_WINDOW < now:
        raise BadRequest("Your email verification expired. Request a new code.")

    business = Business(country="IN", legal_name=company_name, verification_status=BusinessStatus.draft)
    user = User(
        business=business,
        role=UserRole.owner,
        email=email,
        password_hash=hash_password(password),
        account_status=AccountStatus.active,
        email_verified_at=row.verified_at,
        full_name=full_name.strip(),
        position=(position or "").strip() or None,
        session_version=0,
        consent_at=now,
        consent_version=TERMS_VERSION,
        last_login_at=now,
    )
    db.add_all([business, user])
    row.consumed_at = now
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if "legal_name" in str(exc.orig):
            raise Conflict(LEGAL_NAME_TAKEN) from None
        raise Conflict(ACCOUNT_EXISTS) from None
    return user


# ── Login / password ─────────────────────────────────────────────────


async def authenticate(db: AsyncSession, *, email: str, password: str, client: ClientInfo) -> User:
    """Check the password (with lockout), then start the one active session
    (any other device is signed out). Returns the user; the caller sets the
    cookie from ``user.session_token``."""
    user = await db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None or user.deleted_at is not None:
        verify_password(password, _dummy_hash())  # equalise timing
        record_event(db, subject_type="user", subject_id=None, event="login_failed", client=client,
                     details={"reason": "unknown_email"})
        await db.commit()
        raise Unauthorized("Invalid email or password.")
    now = utcnow()
    lockout.ensure_not_locked(user, now)
    if not verify_password(password, user.password_hash):
        locked = lockout.record_failure(user, now)
        record_event(db, subject_type="user", subject_id=user.id, event="login_failed", client=client)
        if locked:
            record_event(db, subject_type="user", subject_id=user.id, event=locked, client=client)
            if locked == "locked_support":
                log.warning("account_locked_support user_id=%s", user.id)
        await db.commit()
        if locked:
            lockout.ensure_not_locked(user, now)
        raise Unauthorized("Invalid email or password.")
    if user.account_status != AccountStatus.active:
        raise Forbidden("This account is disabled. Contact support.")
    lockout.record_success(user)
    user.last_login_at = now
    record_event(db, subject_type="user", subject_id=user.id, event="login_succeeded", client=client)
    return user


async def change_password(
    db: AsyncSession, user: User, *, current_password: str, new_password: str, keep_session: uuid.UUID, client: ClientInfo
) -> User:
    """Rotation: requires the current password; signs out every other
    session (this browser stays signed in)."""
    if not verify_password(current_password, user.password_hash):
        raise Unauthorized("Current password is incorrect.")
    if new_password == current_password:
        raise BadRequest("New password must be different from the current one.")
    user.password_hash = hash_password(new_password)
    user.session_version = (user.session_version or 0) + 1
    await sessions.revoke_all(db, sessions.user_policy(), user.id, "password_changed", keep=keep_session)
    record_event(db, subject_type="user", subject_id=user.id, event="password_changed", client=client)
    await db.commit()
    return user


async def revoke_all_sessions(db: AsyncSession, user: User, client: ClientInfo) -> None:
    await sessions.revoke_all(db, sessions.user_policy(), user.id, "logout_all")
    record_event(db, subject_type="user", subject_id=user.id, event="sessions_revoked", client=client)
    await db.commit()


# ── Password reset ───────────────────────────────────────────────────


async def request_password_reset(db: AsyncSession, *, email: str, client: ClientInfo) -> str | None:
    """Email a reset code if the account exists. Always looks the same to
    the caller (no account enumeration). Returns the code (DEBUG devCode)."""
    email = normalize_email(email)
    user = await db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    purpose = EmailCodePurpose.reset_password
    now = utcnow()
    if user is None or user.account_status != AccountStatus.active:
        return None
    latest = await _latest_code(db, email, purpose)
    if latest is not None and ensure_aware(latest.created_at) + RESEND_COOLDOWN > now:
        return None  # silently throttled
    hour_ago = now - timedelta(hours=1)
    recent = await db.scalar(
        select(func.count()).select_from(EmailCode).where(
            EmailCode.email == email, EmailCode.purpose == purpose, EmailCode.created_at >= hour_ago
        )
    )
    if (recent or 0) >= _hourly_cap():
        return None
    await db.execute(
        update(EmailCode)
        .where(EmailCode.email == email, EmailCode.purpose == purpose, EmailCode.consumed_at.is_(None),
               EmailCode.expires_at > now)
        .values(expires_at=now)
    )
    code = f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"
    db.add(EmailCode(email=email, purpose=purpose, code_hash=hash_code(email, purpose, code), attempts=0,
                     expires_at=now + CODE_TTL, created_at=now))
    record_event(db, subject_type="user", subject_id=user.id, event="password_reset_requested", client=client)
    await db.flush()
    try:
        await notifications.send_password_reset_code(
            to=email, code=code, first_name=notifications.first_name_of(user.full_name),
            valid_minutes=int(CODE_TTL.total_seconds() // 60),
        )
    except Exception:
        await db.rollback()
        log.exception("password_reset_email_failed")
        return None
    await db.commit()
    return code


async def reset_password(db: AsyncSession, *, email: str, code: str, new_password: str, client: ClientInfo) -> None:
    """Code + new password → password replaced, every session signed out,
    temporary lockout cleared. A support lock stays (support must unlock)."""
    email = normalize_email(email)
    code = "".join(ch for ch in code if ch.isdigit())
    purpose = EmailCodePurpose.reset_password
    invalid = "That code is invalid or has expired. Request a new one."
    row = await _latest_code(db, email, purpose)
    now = utcnow()
    if row is None or row.consumed_at is not None or ensure_aware(row.expires_at) <= now:
        raise BadRequest(invalid)
    if row.attempts >= MAX_CODE_ATTEMPTS:
        raise BadRequest("Too many wrong attempts. Request a new code.")
    if not hmac.compare_digest(row.code_hash, hash_code(email, purpose, code)):
        row.attempts += 1
        await db.commit()
        raise BadRequest(invalid)
    user = await db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if user is None or user.account_status != AccountStatus.active:
        raise BadRequest(invalid)
    row.verified_at = now
    row.consumed_at = now
    user.password_hash = hash_password(new_password)
    user.session_version = (user.session_version or 0) + 1
    if not lockout.needs_support(user):
        lockout.record_success(user)
    await sessions.revoke_all(db, sessions.user_policy(), user.id, "password_reset")
    record_event(db, subject_type="user", subject_id=user.id, event="password_reset", client=client)
    await db.commit()
