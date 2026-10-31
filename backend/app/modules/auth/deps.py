"""Current-user resolution — ONLY from the ``cor1x_session`` cookie, looked
up in ``user_sessions`` (server-side; see ``sessions.py``).

(The legacy ``X-User-Id`` header is intentionally not read: seller ids are
public in the catalog, so trusting it allowed impersonation.)
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Cookie, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.errors import Unauthorized
from app.core.logging import set_actor
from app.core.security import SESSION_COOKIE
from app.models.user import AccountStatus, User
from app.modules.auth.sessions import resolve_session, user_policy


async def resolve_session_user(db: AsyncSession, token: str | None) -> tuple[User, uuid.UUID] | None:
    """``(user, session id)`` for a live session, else None."""
    session = await resolve_session(db, user_policy(), token)
    if session is None:
        return None
    user = await db.get(User, session.user_id)
    if user is None or user.deleted_at is not None or user.account_status != AccountStatus.active:
        return None
    return user, session.id


async def get_current_user(
    request: Request,
    cor1x_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    found = await resolve_session_user(db, cor1x_session)
    if found is None:
        raise Unauthorized("Not signed in")
    user, session_id = found
    request.state.session_id = session_id
    set_actor("user", user.id)
    return user


async def get_optional_user(
    cor1x_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    db: AsyncSession = Depends(get_db),
) -> User | None:
    found = await resolve_session_user(db, cor1x_session)
    if found is None:
        return None
    set_actor("user", found[0].id)
    return found[0]


def current_session_id(request: Request, _user: User = Depends(get_current_user)) -> uuid.UUID:
    return request.state.session_id


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]
CurrentSessionId = Annotated[uuid.UUID, Depends(current_session_id)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
