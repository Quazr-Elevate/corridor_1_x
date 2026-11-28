"""0043 on a 0042 database: existing matches and sheets keep working (null
score, no line entries), the score check holds, and it reverses."""
from __future__ import annotations

import sqlite3

import pytest
from test_migration_0020 import _alembic, _build_0019


def test_0043_adds_scores_and_line_entries_and_takes_them_back(tmp_path):
    db = tmp_path / "v42.db"
    _build_0019(db)
    assert _alembic(db, "upgrade", "0042_deal_documents").returncode == 0
    proc = _alembic(db, "upgrade", "0043_rank_and_line_currencies")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    assert {"score", "score_parts"} <= {r[1] for r in con.execute("PRAGMA table_info(rfq_matches)")}
    cols = {r[1]: r for r in con.execute("PRAGMA table_info(cost_sheets)")}
    assert cols["line_entries"][3] == 1 and "{}" in cols["line_entries"][4]  # not null, default {}
    con.execute("PRAGMA foreign_keys = OFF")
    with pytest.raises(sqlite3.IntegrityError, match="ck_rfq_matches_score"):
        con.execute("INSERT INTO rfq_matches (id, rfq_id, seller_business_id, status, source, reasons, score, created_at) "
                    "VALUES ('m', 'r', 's', 'proposed', 'rule', '[]', 101, '2026-01-01')")
    con.close()
    assert _alembic(db, "downgrade", "0042_deal_documents").returncode == 0
    con = sqlite3.connect(db)
    assert "score" not in {r[1] for r in con.execute("PRAGMA table_info(rfq_matches)")}
    con.close()
