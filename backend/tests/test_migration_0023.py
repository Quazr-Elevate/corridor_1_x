"""0023_countries on a 0022-shaped SQLite database: defaults seeded, every
country code already in use seeded (known → reference details, unknown →
paused placeholder), foreign keys added, clean downgrade."""
from __future__ import annotations

import sqlite3
import uuid

import pytest
from test_migration_0020 import _alembic, _build_0019


def test_0023_seeds_used_codes_and_adds_fks(tmp_path):
    db = tmp_path / "v22.db"
    _build_0019(db)  # includes a Saudi (SA) business
    assert _alembic(db, "upgrade", "0022_reject_items").returncode == 0
    con = sqlite3.connect(db)
    con.execute("INSERT INTO businesses (id, country, verification_status) VALUES (?, 'ZZ', 'draft')", (uuid.uuid4().hex,))
    con.commit()
    con.close()

    proc = _alembic(db, "upgrade", "0023_countries")
    assert proc.returncode == 0, proc.stderr

    con = sqlite3.connect(db)
    con.execute("PRAGMA foreign_keys = ON")
    rows = {r[0]: r[1:] for r in con.execute("SELECT code, name, default_currency, active FROM countries")}
    assert rows["IN"] == ("India", "INR", 1) and rows["AE"] == ("United Arab Emirates", "AED", 1)
    assert rows["SA"] == ("Saudi Arabia", "USD", 1)
    assert rows["ZZ"] == ("ZZ", "USD", 0)  # unknown code kept valid, paused for an admin

    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO businesses (id, country, verification_status) VALUES (?, 'QQ', 'draft')", (uuid.uuid4().hex,))
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("DELETE FROM countries WHERE code = 'IN'")
    con.close()

    proc = _alembic(db, "downgrade", "0022_reject_items")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    assert "countries" not in {r[0] for r in con.execute("SELECT name FROM sqlite_master")}
    con.close()
