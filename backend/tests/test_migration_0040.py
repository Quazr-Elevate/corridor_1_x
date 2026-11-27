"""0040_term_sheets on a 0039 database: the table and its freeze trigger
arrive, an issued version's terms can't change, and both go on downgrade."""
from __future__ import annotations

import sqlite3

import pytest
from test_migration_0020 import _alembic, _build_0019

ROW = (
    "INSERT INTO term_sheets (id, deal_id, version, status, product, quantity, unit, incoterm, buyer_price_minor, "
    "buyer_currency, buyer_payment_terms, seller_price_minor, seller_currency, seller_payment_terms, margin_pct, "
    "content_sha256, created_at, updated_at) VALUES (?, 'd', ?, ?, 'Basmati', 100, 'MT', 'FOB', 900, 'AED', "
    "'advance', 800, 'INR', 'advance', 5, ?, '2026-01-01', '2026-01-01')"
)


def test_0040_adds_frozen_term_sheets_and_takes_them_back(tmp_path):
    db = tmp_path / "v39.db"
    _build_0019(db)
    assert _alembic(db, "upgrade", "0039_samples").returncode == 0
    proc = _alembic(db, "upgrade", "0040_term_sheets")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    con.execute("PRAGMA foreign_keys = OFF")
    con.execute(ROW, ("a", 1, "draft", None))
    con.execute("UPDATE term_sheets SET buyer_price_minor = 950 WHERE id = 'a'")  # a draft can change
    with pytest.raises(sqlite3.IntegrityError, match="ck_term_sheets_hashed_when_issued"):
        con.execute(ROW, ("b", 2, "issued", None))
    con.execute("DELETE FROM term_sheets WHERE id = 'a'")
    con.execute(ROW, ("c", 2, "issued", "f" * 64))
    con.execute("UPDATE term_sheets SET buyer_accepted_at = '2026-01-02' WHERE id = 'c'")  # acceptance moves
    with pytest.raises(sqlite3.IntegrityError, match="term_sheet_frozen"):
        con.execute("UPDATE term_sheets SET buyer_price_minor = 1 WHERE id = 'c'")
    con.commit()
    con.close()
    assert _alembic(db, "downgrade", "0039_samples").returncode == 0
    con = sqlite3.connect(db)
    assert con.execute("SELECT count(*) FROM sqlite_master WHERE name LIKE '%term_sheets%'").fetchone() == (0,)
    con.close()
