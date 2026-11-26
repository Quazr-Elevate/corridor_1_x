"""0038_counter_offers on a 0037 database: the table arrives and goes."""
from __future__ import annotations

import sqlite3

from test_migration_0020 import _alembic, _build_0019


def test_0038_adds_counter_offers_and_takes_them_back(tmp_path):
    db = tmp_path / "v37.db"
    _build_0019(db)
    assert _alembic(db, "upgrade", "0037_negotiation_chat").returncode == 0
    proc = _alembic(db, "upgrade", "0038_counter_offers")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    cols = {r[1] for r in con.execute("PRAGMA table_info(counter_offers)")}
    assert {"price_minor", "implied_minor", "margin_pct", "status"} <= cols
    con.close()
    assert _alembic(db, "downgrade", "0037_negotiation_chat").returncode == 0
    con = sqlite3.connect(db)
    assert con.execute("SELECT count(*) FROM sqlite_master WHERE name = 'counter_offers'").fetchone() == (0,)
    con.close()
