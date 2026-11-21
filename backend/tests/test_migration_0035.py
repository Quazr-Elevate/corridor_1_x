"""0035_user_identity_vault on a 0034-shaped SQLite database: every live
user's name, email and phone move to ``user_identities``, a deleted user
gets no vault row, and the downgrade puts the columns back."""
from __future__ import annotations

import sqlite3

from test_migration_0020 import _alembic, _build_0019


def _columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}


def test_0035_moves_people_into_the_vault_and_back(tmp_path):
    db = tmp_path / "v34.db"
    ids = _build_0019(db)
    assert _alembic(db, "upgrade", "0034_credit_expiry_invoices").returncode == 0
    con = sqlite3.connect(db)
    live = dict(con.execute("SELECT id, email FROM users WHERE deleted_at IS NULL"))
    con.execute("UPDATE users SET phone = '+91 98450 00001', phone_normalized = '+919845000001' WHERE id = ?",
                (ids["users"]["sa"],))
    # A deleted account, anonymised the old way.
    deleted = next(iter(live))
    con.execute("UPDATE users SET deleted_at = '2026-11-01 00:00:00' WHERE id = ?", (deleted,))
    con.commit()
    con.close()

    proc = _alembic(db, "upgrade", "0035_user_identity_vault")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    assert not _columns(con, "users") & {"email", "full_name", "phone", "phone_normalized"}
    vault = {row[0]: row[1:] for row in con.execute("SELECT user_id, email, full_name, phone_normalized FROM user_identities")}
    assert set(vault) == set(live) - {deleted}
    assert all(vault[u][0] == live[u] for u in vault)
    assert vault[ids["users"]["sa"]] == ("ksa@grain.sa", "Omar", "+919845000001")
    con.close()

    proc = _alembic(db, "downgrade", "0034_credit_expiry_invoices")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    assert "user_identities" not in {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    back = dict(con.execute("SELECT id, email FROM users"))
    assert all(back[u] == live[u] for u in live if u != deleted)
    assert back[deleted].startswith("deleted-") and back[deleted].endswith("@deleted.local")
    assert con.execute("SELECT full_name FROM users WHERE id = ?", (deleted,)).fetchone() == ("Deleted user",)
    con.close()

    assert _alembic(db, "upgrade", "0035_user_identity_vault").returncode == 0
