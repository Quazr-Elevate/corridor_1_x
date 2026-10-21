"""Alembic environment.

Loads DATABASE_URL from Settings and runs migrations on an async engine via
a sync-adapter thread (Alembic itself is sync). ``render_as_batch`` is on for
SQLite so ALTER-style operations in new migrations are portable (SQLite
recreates the table when needed).

Note: revisions 0010–0017 use Postgres-only features and cannot run on
SQLite — create a local SQLite DB with ``python -m scripts.init_local_db``
(create_all + ``alembic stamp head``) instead. Migrations from 0018 on must
run on both dialects.
"""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

import app.models  # noqa: F401 — registers every model on Base.metadata
from app.core.config import settings
from app.models.base import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Respect an explicitly passed URL (tests / init script); default to settings.
if not config.get_main_option("sqlalchemy.url"):
    # ConfigParser interpolation: a literal '%' (e.g. in a password) must be doubled.
    config.set_main_option("sqlalchemy.url", settings.resolved_database_url.replace("%", "%%"))

target_metadata = Base.metadata


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_is_sqlite(url),
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
