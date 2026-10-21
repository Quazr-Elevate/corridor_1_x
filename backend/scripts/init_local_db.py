"""Create a fresh local SQLite database at the current schema.

Revisions 0010–0017 use Postgres-only DDL, so ``alembic upgrade head``
can't build a SQLite DB from scratch. Instead this script runs
``Base.metadata.create_all`` and then ``alembic stamp head`` so later
migrations (0018+, which are dialect-portable) apply normally.

Usage (from anywhere)::

    backend/.venv/bin/python backend/scripts/init_local_db.py            # DATABASE_URL from .env
    backend/.venv/bin/python backend/scripts/init_local_db.py --force    # delete + recreate
    backend/.venv/bin/python backend/scripts/init_local_db.py --database-url sqlite+aiosqlite:////tmp/x.db
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

import app.models  # noqa: E402,F401 — registers all tables
from app.core.config import settings  # noqa: E402
from app.models.base import Base  # noqa: E402


def alembic_config(url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def sqlite_file(url: str) -> Path | None:
    prefix = "sqlite+aiosqlite:///"
    return Path(url[len(prefix):]) if url.startswith(prefix) else None


async def _create_all(url: str) -> None:
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


def init_db(url: str, *, force: bool = False) -> None:
    if not url.startswith("sqlite"):
        raise SystemExit("init_local_db only targets SQLite. For Postgres run: alembic upgrade head")
    path = sqlite_file(url)
    if path is not None and path.exists():
        if not force:
            raise SystemExit(f"{path} already exists — pass --force to delete and recreate it.")
        path.unlink()
    asyncio.run(_create_all(url))
    command.stamp(alembic_config(url), "head")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--database-url", default=None, help="defaults to DATABASE_URL from settings")
    parser.add_argument("--force", action="store_true", help="delete an existing SQLite file first")
    args = parser.parse_args()
    url = args.database_url or settings.resolved_database_url
    init_db(url, force=args.force)
    print(f"Initialised {url} (stamped at alembic head)")


if __name__ == "__main__":
    main()
