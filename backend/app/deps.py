from uuid import UUID

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.user import User
from app.user_session import SESSION_COOKIE, decode_session


async def get_current_user(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    cor1x_session: str | None = Cookie(default=None, alias=SESSION_COOKIE),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the current signed-in user.

    Two paths, in order of precedence:
    1. `X-User-Id` header — legacy, still honoured for backwards-compat with
       the dashboard code the pulled commit shipped (localStorage-based).
    2. `cor1x_session` HttpOnly cookie — the new default, set by /otp/verify
       (login) and /auth/signup. Signed via itsdangerous, 24-hour TTL.

    Soft-deleted users (users.deleted_at set) are treated as unauthenticated.
    """
    user_id_str: str | None = x_user_id or (
        decode_session(cor1x_session) if cor1x_session else None
    )
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not signed in",
        )
    try:
        user_uuid = UUID(user_id_str)
    except ValueError as e:
        raise HTTPException(status_code=401, detail="Invalid user id") from e
    user = await db.get(User, user_uuid)
    if not user or user.deleted_at is not None:
        raise HTTPException(status_code=401, detail="Unknown user")
    return user
