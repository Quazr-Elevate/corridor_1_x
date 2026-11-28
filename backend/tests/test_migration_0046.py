"""0046 on a 0045 database: the banking tables and the cooling-off setting, reversibly."""
from __future__ import annotations

import sqlite3

from test_migration_0020 import _alembic, _build_0019

TABLES = ("bank_accounts", "bank_statement_maps", "bank_statements", "bank_statement_lines")


def test_0046_adds_banking_and_takes_it_back(tmp_path):
    db = tmp_path / "v45.db"
    _build_0019(db)
    assert _alembic(db, "upgrade", "0045_payment_milestones").returncode == 0
    proc = _alembic(db, "upgrade", "0046_banking")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert set(TABLES) <= names
    assert con.execute("SELECT value FROM trade_settings WHERE key = 'payout_cooling_off_hours'").fetchone()[0] == 72
    con.close()
    assert _alembic(db, "downgrade", "0045_payment_milestones").returncode == 0
    con = sqlite3.connect(db)
    names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert not set(TABLES) & names
    con.close()
