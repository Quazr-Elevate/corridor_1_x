from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


def _make_engine():
    """Async engine tuned for Railway Postgres over the public internet.

    Notes:
      * pool_pre_ping keeps SQLite dev happy and cheaply detects stale
        connections dropped by the Railway proxy after idle timeouts.
      * The default asyncpg pool is tiny (5) — bump it so a burst of parallel
        requests (which the frontend fires on every page load) doesn't
        serialize behind the pool.
      * pool_recycle avoids the "server closed the connection unexpectedly"
        after long idle.
    """
    if settings.resolved_database_url.startswith("sqlite"):
        return create_async_engine(
            settings.resolved_database_url,
            echo=False,
            pool_pre_ping=True,
        )
    return create_async_engine(
        settings.resolved_database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=15,
        max_overflow=15,
        pool_recycle=1800,
    )


engine = _make_engine()
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
