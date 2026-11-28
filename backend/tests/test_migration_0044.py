"""0044_trade_ledger on a 0043 database: the ledger arrives append-only and
goes on downgrade."""
from __future__ import annotations

import sqlite3

import pytest
from test_migration_0020 import _alembic, _build_0019


def test_0044_adds_an_append_only_ledger_and_takes_it_back(tmp_path):
    db = tmp_path / "v43.db"
    _build_0019(db)
    assert _alembic(db, "upgrade", "0043_rank_and_line_currencies").returncode == 0
    proc = _alembic(db, "upgrade", "0044_trade_ledger")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    con.execute("PRAGMA foreign_keys = OFF")
    con.execute("INSERT INTO ledger_transactions (id, kind, memo, idempotency_key, created_at) "
                "VALUES ('t', 'test', 'x', 'k', '2026-01-01')")
    con.execute("INSERT INTO ledger_entries (id, transaction_id, account, amount_minor, currency, created_at) "
                "VALUES ('e', 't', 'bank', 100, 'INR', '2026-01-01')")
    with pytest.raises(sqlite3.IntegrityError, match="ck_ledger_entries_account"):
        con.execute("INSERT INTO ledger_entries (id, transaction_id, account, amount_minor, currency, created_at) "
                    "VALUES ('f', 't', 'cash_box', -100, 'INR', '2026-01-01')")
    for stmt in ("UPDATE ledger_entries SET amount_minor = 1", "DELETE FROM ledger_entries",
                 "UPDATE ledger_transactions SET memo = 'y'", "DELETE FROM ledger_transactions"):
        with pytest.raises(sqlite3.IntegrityError, match="ledger_insert_only"):
            con.execute(stmt)
    con.close()
    assert _alembic(db, "downgrade", "0043_rank_and_line_currencies").returncode == 0
    con = sqlite3.connect(db)
    assert con.execute("SELECT count(*) FROM sqlite_master WHERE name LIKE 'ledger_%'").fetchone() == (0,)
    con.close()
