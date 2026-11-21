"""0032_trader_sessions and 0033_country_rules on a 0031-shaped SQLite
database: the session and company-name indexes stop being unique, India's
rule and links are seeded, PAN is shared, the templates arrive, and the
downgrade puts it back."""
from __future__ import annotations

import sqlite3

from test_migration_0020 import _alembic, _build_0019


def _index(con: sqlite3.Connection, name: str) -> str | None:
    row = con.execute("SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?", (name,)).fetchone()
    return row[0] if row else None


def test_0032_and_0033_upgrade_and_downgrade(tmp_path):
    db = tmp_path / "v31.db"
    _build_0019(db)
    assert _alembic(db, "upgrade", "0031_desk_limits").returncode == 0
    proc = _alembic(db, "upgrade", "0033_country_rules")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    assert _index(con, "uq_user_sessions_one_active") is None and "UNIQUE" not in (_index(con, "ix_user_sessions_active") or "")
    assert _index(con, "uq_business_identities_legal_name_normalized") is None
    assert con.execute("SELECT source_start, source_end FROM country_document_rules WHERE country = 'IN'").fetchall() == [(3, 12)]
    assert con.execute(
        "SELECT t.code FROM countries c JOIN kyb_document_types t ON t.id = c.group_document_type_id WHERE c.code = 'IN'"
    ).fetchone() == ("pan",)
    assert con.execute("SELECT is_unique FROM kyb_document_types WHERE country = 'IN' AND code = 'pan'").fetchone() == (0,)
    assert con.execute("SELECT count(*) FROM spec_parameters WHERE category = 'Coffee'").fetchone() == (5,)
    assert con.execute("SELECT count(*) FROM category_certificate_requirements").fetchone() == (12,)
    con.close()

    proc = _alembic(db, "downgrade", "0031_desk_limits")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    assert "UNIQUE" in _index(con, "uq_user_sessions_one_active")
    assert "UNIQUE" in _index(con, "uq_business_identities_legal_name_normalized")
    assert con.execute("SELECT is_unique FROM kyb_document_types WHERE country = 'IN' AND code = 'pan'").fetchone() == (1,)
    assert con.execute("SELECT count(*) FROM spec_parameters WHERE category = 'Coffee'").fetchone() == (0,)
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert not {"country_document_rules", "category_certificate_requirements"} & tables
    con.close()
