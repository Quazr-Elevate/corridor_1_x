"""Async SQLAlchemy engine + session factory."""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


def _make_engine():
    """Async engine tuned for Railway Postgres over the public internet.

    * pool_pre_ping cheaply detects connections dropped by the proxy.
    * The asyncpg pool is bumped so the frontend's burst of parallel
      requests on every page load doesn't serialize behind the pool.
    * pool_recycle avoids "server closed the connection" after long idle.
    * statement_timeout cancels any statement that runs too long, so a stuck
      query can't hold a connection and starve the pool.

    Pool sizing: each process may hold up to pool_size + max_overflow (30)
    connections. With several workers/replicas keep
    processes × 30 below Postgres's max_connections (or add PgBouncer).

    SQLite: foreign keys are OFF by default and must be enabled on every
    connection, otherwise ON DELETE CASCADE / RESTRICT / SET NULL and FK
    checks silently don't happen locally (Postgres always enforces them).
    """
    url = settings.resolved_database_url
    if url.startswith("sqlite"):
        eng = create_async_engine(url, echo=False, pool_pre_ping=True)

        @event.listens_for(eng.sync_engine, "connect")
        def _sqlite_foreign_keys(dbapi_conn, _record):  # pragma: no cover - trivial
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        return eng

    connect_args = {}
    if settings.db_statement_timeout_ms > 0:
        connect_args["server_settings"] = {
            "statement_timeout": str(settings.db_statement_timeout_ms)
        }
    return create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        pool_size=15,
        max_overflow=15,
        pool_recycle=1800,
        connect_args=connect_args,
    )


engine = _make_engine()
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def ping_db() -> bool:
    """``SELECT 1`` — True when the database answers."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 — any failure means "down"
        return False
