"""0030_quotes_offers on a 0029-shaped SQLite database: the four tables
arrive and the downgrade removes them."""
from __future__ import annotations

import sqlite3

from test_migration_0020 import _alembic, _build_0019

TABLES = {"quotes", "cost_sheets", "offers", "offer_unlocks"}


def test_0030_creates_quotes_cost_sheets_and_offers(tmp_path):
    db = tmp_path / "v29.db"
    _build_0019(db)
    assert _alembic(db, "upgrade", "0029_deals_rfqs").returncode == 0
    proc = _alembic(db, "upgrade", "0030_quotes_offers")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    assert TABLES <= {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    # The buyer's record has no column for what Corridor One X pays.
    offer_columns = {r[1] for r in con.execute("PRAGMA table_info(offers)")}
    assert not [c for c in offer_columns if "purchase" in c or "margin" in c or "cost" in c.replace("cost_sheet_id", "")]
    sheet_sql = con.execute("SELECT sql FROM sqlite_master WHERE name = 'cost_sheets'").fetchone()[0]
    assert "ck_cost_sheets_second_approver" in sheet_sql
    con.close()
    proc = _alembic(db, "downgrade", "0029_deals_rfqs")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    assert not TABLES & {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    con.close()
