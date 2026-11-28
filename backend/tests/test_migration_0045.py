"""0045 on a 0044 database: payment milestones and the two new settings, reversibly."""
from __future__ import annotations

import sqlite3

from test_migration_0020 import _alembic, _build_0019


def test_0045_adds_milestones_and_settings_and_takes_them_back(tmp_path):
    db = tmp_path / "v44.db"
    _build_0019(db)
    assert _alembic(db, "upgrade", "0044_trade_ledger").returncode == 0
    proc = _alembic(db, "upgrade", "0045_payment_milestones")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    rows = dict(con.execute("SELECT key, is_placeholder FROM trade_settings WHERE key IN ('outlay_cap_months', 'retention_pct')"))
    assert rows == {"outlay_cap_months": 1, "retention_pct": 1}
    assert "gate" in {r[1] for r in con.execute("PRAGMA table_info(payment_milestones)")}
    con.close()
    assert _alembic(db, "downgrade", "0044_trade_ledger").returncode == 0
    con = sqlite3.connect(db)
    assert con.execute("SELECT count(*) FROM sqlite_master WHERE name = 'payment_milestones'").fetchone() == (0,)
    assert con.execute("SELECT count(*) FROM trade_settings WHERE key = 'retention_pct'").fetchone() == (0,)
    con.close()
