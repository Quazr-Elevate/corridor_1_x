"""Server-side sessions (users and admins) + the sign-in event log.

A trader keeps up to ``USER_MAX_SESSIONS`` live sessions (five, A-044): the
next sign-in signs out the oldest (``replaced``). An admin keeps one, held by
a partial unique index. A session ends at the first of:

* idle timeout — no request for ``idle`` (traders 12h, admins 30m);
* absolute timeout — ``expires_at`` (traders 7d, admins 8h);
* revocation — logout, new sign-in elsewhere, password change/reset,
  account deletion or disabling, an admin's "sign out".
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_token, ip_prefix, new_session_token
from app.core.time import ensure_aware, utcnow
from app.models.auth_session import AdminSession, AuthEvent, UserSession
from app.ratelimit import client_ip

log = logging.getLogger("app.auth")

#: ``last_seen_at`` is written at most this often (keeps reads cheap).
TOUCH_EVERY = timedelta(seconds=60)

SessionModel = type[UserSession] | type[AdminSession]


# ── Client info ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class ClientInfo:
    ip: str | None  # full address — only for the allowlist check, never stored
    ip_prefix: str | None
    user_agent: str | None


def client_info(request: Request) -> ClientInfo:
    ip = client_ip(request)
    ua = (request.headers.get("user-agent") or "").strip()[:200] or None
    return ClientInfo(ip=ip, ip_prefix=ip_prefix(ip), user_agent=ua)


Client = Annotated[ClientInfo, Depends(client_info)]


# ── Devices ──────────────────────────────────────────────────────────

_VERSION = re.compile(r"[\d._]+")
_BROWSERS = (("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("Chrome/", "Chrome"), ("Safari/", "Safari"))
_SYSTEMS = (
    ("Android", "Android"), ("iPhone", "iPhone"), ("iPad", "iPad"), ("Windows", "Windows"),
    ("Mac OS X", "Mac"), ("Linux", "Linux"),
)


def device_key(user_agent: str | None) -> str:
    """The user agent without version numbers, so a browser update is not a
    "new device". Empty when the client sent none."""
    return _VERSION.sub("", user_agent or "").strip()


def device_label(user_agent: str | None) -> str:
    """Short description for an email, e.g. ``Chrome on Windows``."""
    ua = user_agent or ""
    browser = next((name for token, name in _BROWSERS if token in ua), None)
    system = next((name for token, name in _SYSTEMS if token in ua), None)
    if browser and system:
        return f"{browser} on {system}"
    return browser or system or "An unrecognised browser"


async def is_new_device(db: AsyncSession, subject_type: str, subject_id: uuid.UUID, client: ClientInfo) -> bool:
    """True when the account has signed in before, but never from this kind
    of browser. Call it before recording the current sign-in."""
    seen = set(
        await db.scalars(
            select(AuthEvent.user_agent)
            .where(
                AuthEvent.subject_type == subject_type,
                AuthEvent.subject_id == subject_id,
                AuthEvent.event == "login_succeeded",
            )
            .distinct()
        )
    )
    return bool(seen) and device_key(client.user_agent) not in {device_key(ua) for ua in seen}


# ── Policy ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Policy:
    model: Any
    owner_col: str
    subject_type: str
    idle: timedelta
    absolute: timedelta
    max_active: int = 1


def user_policy() -> Policy:
    return Policy(
        UserSession, "user_id", "user",
        timedelta(hours=settings.user_session_idle_hours), timedelta(days=settings.user_session_max_days),
        max_active=max(1, settings.user_max_sessions),
    )


def admin_policy() -> Policy:
    return Policy(
        AdminSession, "admin_user_id", "admin",
        timedelta(minutes=settings.admin_session_idle_minutes), timedelta(hours=settings.admin_session_max_hours),
    )


# ── Events ───────────────────────────────────────────────────────────


def record_event(
    db: AsyncSession,
    *,
    subject_type: str,
    subject_id: uuid.UUID | None,
    event: str,
    client: ClientInfo | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Stage an ``auth_events`` row in the caller's transaction."""
    db.add(
        AuthEvent(
            subject_type=subject_type,
            subject_id=subject_id,
            event=event,
            ip_prefix=client.ip_prefix if client else None,
            user_agent=client.user_agent if client else None,
            details=details,
            created_at=utcnow(),
        )
    )


# ── Lifecycle ────────────────────────────────────────────────────────


async def revoke_all(
    db: AsyncSession, policy: Policy, subject_id: uuid.UUID, reason: str, *, keep: uuid.UUID | None = None
) -> int:
    """Revoke every active session of the account (except ``keep``).
    Staged in the caller's transaction; returns how many were active."""
    m = policy.model
    stmt = (
        update(m)
        .where(getattr(m, policy.owner_col) == subject_id, m.revoked_at.is_(None))
        .values(revoked_at=utcnow(), revoked_reason=reason)
    )
    if keep is not None:
        stmt = stmt.where(m.id != keep)
    result = await db.execute(stmt.execution_options(synchronize_session="fetch"))
    return result.rowcount or 0


def _is_live(row: Any, policy: Policy, now) -> bool:
    return ensure_aware(row.expires_at) > now and ensure_aware(row.last_seen_at) + policy.idle > now


async def _make_room(db: AsyncSession, policy: Policy, subject_id: uuid.UUID) -> int:
    """Before a new sign-in: close sessions that have run out, then sign out
    the oldest live ones until the new session fits under the limit.
    Returns how many live sessions were signed out."""
    if policy.max_active == 1:
        return await revoke_all(db, policy, subject_id, "replaced")
    m = policy.model
    now = utcnow()
    open_rows = list(await db.scalars(
        select(m).where(getattr(m, policy.owner_col) == subject_id, m.revoked_at.is_(None)).order_by(m.created_at)
    ))
    live = []
    for row in open_rows:
        if _is_live(row, policy, now):
            live.append(row)
        else:
            row.revoked_at, row.revoked_reason = now, "expired"
    over = len(live) - (policy.max_active - 1)
    for row in live[:max(over, 0)]:
        row.revoked_at, row.revoked_reason = now, "replaced"
    return max(over, 0)


async def start_session(
    db: AsyncSession, policy: Policy, subject_id: uuid.UUID, client: ClientInfo
) -> tuple[str, Any]:
    """Make room under the policy's limit, create a new session, commit.
    Returns ``(cookie token, session row)``."""
    for attempt in (1, 2):
        replaced = await _make_room(db, policy, subject_id)
        now = utcnow()
        token, token_hash = new_session_token()
        row = policy.model(
            **{policy.owner_col: subject_id},
            token_hash=token_hash,
            created_at=now,
            last_seen_at=now,
            expires_at=now + policy.absolute,
            ip_prefix=client.ip_prefix,
            user_agent=client.user_agent,
        )
        db.add(row)
        if replaced:
            record_event(db, subject_type=policy.subject_type, subject_id=subject_id, event="session_replaced", client=client)
        try:
            await db.commit()
            return token, row
        except IntegrityError:
            # A concurrent admin sign-in won the one-active-session index; retry once.
            await db.rollback()
            if attempt == 2:
                raise
    raise AssertionError("unreachable")


async def resolve_session(db: AsyncSession, policy: Policy, token: str | None) -> Any | None:
    """The live session for a cookie token, or None (unknown, revoked, idle
    or past its absolute cap). Refreshes ``last_seen_at`` (≤ once a minute)."""
    if not token or len(token) > 200:
        return None
    m = policy.model
    row = await db.scalar(select(m).where(m.token_hash == hash_token(token)))
    if row is None or row.revoked_at is not None:
        return None
    now = utcnow()
    if ensure_aware(row.expires_at) <= now:
        return None
    last_seen = ensure_aware(row.last_seen_at)
    if last_seen + policy.idle <= now:
        return None
    if now - last_seen >= TOUCH_EVERY:
        row.last_seen_at = now
        await db.commit()
    return row


async def end_session(db: AsyncSession, policy: Policy, token: str | None, client: ClientInfo) -> None:
    """Logout: revoke this browser's session (no-op if already gone)."""
    if not token or len(token) > 200:
        return
    m = policy.model
    row = await db.scalar(select(m).where(m.token_hash == hash_token(token), m.revoked_at.is_(None)))
    if row is None:
        return
    row.revoked_at = utcnow()
    row.revoked_reason = "logout"
    record_event(
        db, subject_type=policy.subject_type, subject_id=getattr(row, policy.owner_col), event="logout", client=client
    )
    await db.commit()


async def live_sessions(db: AsyncSession, policy: Policy, subject_id: uuid.UUID) -> list[Any]:
    """The account's live sessions, most recently used first."""
    m = policy.model
    now = utcnow()
    rows = await db.scalars(
        select(m).where(getattr(m, policy.owner_col) == subject_id, m.revoked_at.is_(None)).order_by(m.last_seen_at.desc())
    )
    return [r for r in rows if _is_live(r, policy, now)]


async def revoke_one(
    db: AsyncSession, policy: Policy, subject_id: uuid.UUID, session_id: uuid.UUID, client: ClientInfo
) -> bool:
    """Sign one of the account's own sessions out. False when there is no
    such live session (another account's, or already ended)."""
    m = policy.model
    row = await db.scalar(
        select(m).where(m.id == session_id, getattr(m, policy.owner_col) == subject_id, m.revoked_at.is_(None))
    )
    if row is None:
        return False
    row.revoked_at, row.revoked_reason = utcnow(), "signed_out_elsewhere"
    record_event(db, subject_type=policy.subject_type, subject_id=subject_id, event="session_signed_out", client=client)
    await db.commit()
    return True


async def active_session(db: AsyncSession, policy: Policy, subject_id: uuid.UUID) -> Any | None:
    """The account's most recently used live session, or None."""
    live = await live_sessions(db, policy, subject_id)
    return live[0] if live else None


def cookie_max_age(policy: Policy) -> int:
    return int(policy.absolute.total_seconds())
