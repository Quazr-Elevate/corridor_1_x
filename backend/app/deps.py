from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.user import User


async def get_current_user(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Simple session dep for now: trusts an X-User-Id header set by the
    frontend from localStorage after /auth/verify. This will move to a
    proper JWT + HttpOnly cookie later; keeping the interface stable so
    that swap doesn't ripple through routers.
    """
    if not x_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Id header",
        )
    try:
        user_uuid = UUID(x_user_id)
    except ValueError as e:
        raise HTTPException(status_code=401, detail="Invalid user id") from e
    user = await db.get(User, user_uuid)
    if not user:
        raise HTTPException(status_code=401, detail="Unknown user")
    return user
