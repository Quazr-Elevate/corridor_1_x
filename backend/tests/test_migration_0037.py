"""0037_negotiation_chat on a 0036-shaped SQLite database: the chat tables,
the strikes table and the new columns arrive; downgrade removes them."""
from __future__ import annotations

import sqlite3

from test_migration_0020 import _alembic, _build_0019


def _tables(con: sqlite3.Connection) -> set[str]:
    return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def _columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}


def test_0037_adds_negotiation_and_takes_it_back(tmp_path):
    db = tmp_path / "v36.db"
    _build_0019(db)
    assert _alembic(db, "upgrade", "0036_single_address").returncode == 0
    proc = _alembic(db, "upgrade", "0037_negotiation_chat")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    assert {"chat_threads", "chat_messages", "leak_strikes"} <= _tables(con)
    assert {"suspended_at", "suspended_reason"} <= _columns(con, "businesses")
    assert "chosen_offer_id" in _columns(con, "deals")
    assert "not_chosen" in con.execute("SELECT sql FROM sqlite_master WHERE name = 'offers'").fetchone()[0]
    con.close()

    proc = _alembic(db, "downgrade", "0036_single_address")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    assert not {"chat_threads", "chat_messages", "leak_strikes"} & _tables(con)
    assert "suspended_at" not in _columns(con, "businesses") and "chosen_offer_id" not in _columns(con, "deals")
    con.close()
    assert _alembic(db, "upgrade", "0037_negotiation_chat").returncode == 0
