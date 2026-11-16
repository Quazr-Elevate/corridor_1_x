"""0029_deals_rfqs on a 0028-shaped SQLite database: the deal and RFQ tables
arrive with the seeded desk settings, the held-countries list starts empty,
and the downgrade removes them."""
from __future__ import annotations

import sqlite3

from test_migration_0020 import _alembic, _build_0019

TABLES = {"deals", "deal_events", "rfqs", "rfq_matches", "held_countries", "trade_settings"}


def test_0029_creates_the_deal_and_rfq_tables(tmp_path):
    db = tmp_path / "v28.db"
    _build_0019(db)
    assert _alembic(db, "upgrade", "0028_credits").returncode == 0
    proc = _alembic(db, "upgrade", "0029_deals_rfqs")
    assert proc.returncode == 0, proc.stderr

    con = sqlite3.connect(db)
    assert TABLES <= {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    settings = {k: (float(v), bool(p)) for k, v, p in con.execute("SELECT key, value, is_placeholder FROM trade_settings")}
    assert settings == {
        "rfq_open_days": (14.0, True), "quote_valid_days": (7.0, True), "min_margin_pct": (5.0, True),
        "fx_buffer_pct": (2.0, True), "freight_max_age_days": (7.0, False),
    }
    assert con.execute("SELECT COUNT(*) FROM held_countries").fetchone()[0] == 0  # the list is the client's
    con.close()

    proc = _alembic(db, "downgrade", "0028_credits")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    assert not TABLES & {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    con.close()
