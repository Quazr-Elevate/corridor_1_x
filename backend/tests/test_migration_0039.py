"""0039_samples on a 0038 database: the tables arrive, the seal check holds,
and both go on downgrade."""
from __future__ import annotations

import sqlite3

import pytest
from test_migration_0020 import _alembic, _build_0019


def test_0039_adds_samples_and_takes_them_back(tmp_path):
    db = tmp_path / "v38.db"
    _build_0019(db)
    assert _alembic(db, "upgrade", "0038_counter_offers").returncode == 0
    proc = _alembic(db, "upgrade", "0039_samples")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    cols = {r[1] for r in con.execute("PRAGMA table_info(samples)")}
    assert {"status", "retained_seal_no", "forward_seal_no", "seller_courier_ref", "forward_courier_ref", "verdict"} <= cols
    assert {r[1] for r in con.execute("PRAGMA table_info(sample_events)")} >= {"from_status", "to_status", "actor_type"}
    # No deal rows here, so check the seal rule with foreign keys off.
    con.execute("PRAGMA foreign_keys = OFF")
    row = "INSERT INTO samples (id, deal_id, status, created_at, updated_at) VALUES (?, 'b', ?, '2026-01-01', '2026-01-01')"
    con.execute(row, ("a", "requested"))
    with pytest.raises(sqlite3.IntegrityError, match="ck_samples_sealed_before_forward"):
        con.execute(row, ("c", "forwarded"))
    con.close()
    assert _alembic(db, "downgrade", "0038_counter_offers").returncode == 0
    con = sqlite3.connect(db)
    assert con.execute("SELECT count(*) FROM sqlite_master WHERE name IN ('samples', 'sample_events')").fetchone() == (0,)
    con.close()
