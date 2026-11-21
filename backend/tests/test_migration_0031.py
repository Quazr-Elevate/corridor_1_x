"""0031_desk_limits on a 0030-shaped SQLite database: the two settings and
the new columns arrive, one live offer per sheet is enforced, and the
downgrade puts everything back."""
from __future__ import annotations

import sqlite3

from test_migration_0020 import _alembic, _build_0019


def _index_sql(con: sqlite3.Connection, name: str) -> str | None:
    row = con.execute("SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?", (name,)).fetchone()
    return row[0] if row else None


def test_0031_adds_the_desk_limits_and_the_live_offer_index(tmp_path):
    db = tmp_path / "v30.db"
    _build_0019(db)
    assert _alembic(db, "upgrade", "0030_quotes_offers").returncode == 0
    proc = _alembic(db, "upgrade", "0031_desk_limits")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    settings = dict(con.execute("SELECT key, is_placeholder FROM trade_settings WHERE key IN ('max_margin_pct', 'fx_max_age_days')"))
    assert settings == {"max_margin_pct": 1, "fx_max_age_days": 1}
    assert {"max_margin_pct", "approval_reasons"} <= {r[1] for r in con.execute("PRAGMA table_info(cost_sheets)")}
    assert "expiry_reminded_at" in {r[1] for r in con.execute("PRAGMA table_info(offers)")}
    assert "status <> 'withdrawn'" in _index_sql(con, "uq_offers_cost_sheet_live")
    con.close()

    proc = _alembic(db, "downgrade", "0030_quotes_offers")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    assert con.execute("SELECT count(*) FROM trade_settings WHERE key IN ('max_margin_pct', 'fx_max_age_days')").fetchone() == (0,)
    assert "approval_reasons" not in {r[1] for r in con.execute("PRAGMA table_info(cost_sheets)")}
    assert _index_sql(con, "uq_offers_cost_sheet_live") is None
    assert "uq_offers_cost_sheet_id" in con.execute("SELECT sql FROM sqlite_master WHERE name = 'offers'").fetchone()[0]
    con.close()
