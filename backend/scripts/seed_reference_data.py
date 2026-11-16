"""Seed the reference data a usable database needs: onboarding countries
and their KYB document types.

In production these rows arrive with migrations 0021 / 0023. A local SQLite
database built by ``init_local_db.py`` is *stamped* at head rather than
migrated, so those inserts never run and the tables come up empty — and an
empty ``countries`` table makes signup fail (the business row references a
country), which surfaces as a confusing "account already exists".

Run it after ``init_local_db.py``; it is idempotent, so running it again on
a live database only adds what is missing and never overwrites an edit ops
made in the console.

Usage::

    backend/.venv/bin/python backend/scripts/seed_reference_data.py
    backend/.venv/bin/python backend/scripts/seed_reference_data.py --database-url sqlite+aiosqlite:////tmp/x.db
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.models  # noqa: E402,F401 — registers all tables
from app.core.config import settings  # noqa: E402
from app.models.country import Country  # noqa: E402
from app.models.kyb_document_type import KybDocumentType  # noqa: E402
from app.modules.verification.seed import default_country_rows, default_rows  # noqa: E402


async def seed(url: str) -> tuple[int, int]:
    engine = create_async_engine(url)
    session = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session() as db:
            have_countries = set(await db.scalars(select(Country.code)))
            new_countries = [row for row in default_country_rows() if row["code"] not in have_countries]
            if new_countries:
                await db.execute(Country.__table__.insert(), new_countries)

            have_types = {
                (country, code)
                for country, code in (await db.execute(select(KybDocumentType.country, KybDocumentType.code))).all()
            }
            new_types = [row for row in default_rows() if (row["country"], row["code"]) not in have_types]
            if new_types:
                await db.execute(KybDocumentType.__table__.insert(), new_types)

            await db.commit()
        return len(new_countries), len(new_types)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--database-url", default=None, help="defaults to DATABASE_URL from settings")
    args = parser.parse_args()
    url = args.database_url or settings.resolved_database_url
    countries, types_ = asyncio.run(seed(url))
    print(f"Seeded {countries} countries and {types_} KYB document types into {url}")


if __name__ == "__main__":
    main()
