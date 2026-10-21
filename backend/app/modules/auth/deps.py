"""Current-user resolution — ONLY from the signed ``cor1x_session`` cookie.

(The legacy ``X-User-Id`` header is intentionally not read: seller ids are
public in the catalog, so trusting it allowed impersonation.)
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.errors import Unauthorized
from app.core.security import SESSION_COOKIE, decode_session_token
from app.models.user import AccountStatus, User


async def resolve_session_user(db: AsyncSession, token: str | None) -> User | None:
    claims = decode_session_token(token)
    if claims is None:
        return None
    user = await db.get(User, claims.user_id)
    if user is None or user.deleted_at is not None or user.account_status != AccountStatus.active:
        return None
    if user.session_version != claims.session_version:
        return None  # revoked (password change / logout-everywhere)
    return user


async def get_current_user(
    cor1x_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    user = await resolve_session_user(db, cor1x_session)
    if user is None:
        raise Unauthorized("Not signed in")
    return user


async def get_optional_user(
    cor1x_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    db: AsyncSession = Depends(get_db),
) -> User | None:
    return await resolve_session_user(db, cor1x_session)


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
