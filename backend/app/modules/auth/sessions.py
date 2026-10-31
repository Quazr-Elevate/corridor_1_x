"""Server-side sessions (users and admins) + the sign-in event log.

One active session per account: :func:`start_session` revokes whatever is
active (``replaced``) before inserting the new row, and a partial unique
index enforces it in the database. A session ends at the first of:

* idle timeout — no request for ``idle`` (traders 12h, admins 30m);
* absolute timeout — ``expires_at`` (traders 7d, admins 8h);
* revocation — logout, new sign-in elsewhere, password change/reset,
  account deletion or disabling, an admin's "sign out".
"""
from __future__ import annotations

import logging
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


# ── Policy ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Policy:
    model: Any
    owner_col: str
    subject_type: str
    idle: timedelta
    absolute: timedelta


def user_policy() -> Policy:
    return Policy(
        UserSession, "user_id", "user",
        timedelta(hours=settings.user_session_idle_hours), timedelta(days=settings.user_session_max_days),
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


async def start_session(
    db: AsyncSession, policy: Policy, subject_id: uuid.UUID, client: ClientInfo
) -> tuple[str, Any]:
    """Revoke the active session (if any), create a new one, commit.
    Returns ``(cookie token, session row)``."""
    for attempt in (1, 2):
        replaced = await revoke_all(db, policy, subject_id, "replaced")
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
            # A concurrent sign-in won the one-active-session index; retry once.
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


async def active_session(db: AsyncSession, policy: Policy, subject_id: uuid.UUID) -> Any | None:
    m = policy.model
    row = await db.scalar(select(m).where(getattr(m, policy.owner_col) == subject_id, m.revoked_at.is_(None)))
    if row is None:
        return None
    now = utcnow()
    if ensure_aware(row.expires_at) <= now or ensure_aware(row.last_seen_at) + policy.idle <= now:
        return None
    return row


def cookie_max_age(policy: Policy) -> int:
    return int(policy.absolute.total_seconds())
