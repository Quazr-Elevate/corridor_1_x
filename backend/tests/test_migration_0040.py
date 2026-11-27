"""0040_no_builtin_india_checks on a 0039 database: the seeded GSTIN and PAN
formats and the GSTIN 3–12 = PAN rule are switched off, an admin's own
pattern is kept, and downgrade puts the seeded values back."""
from __future__ import annotations

import sqlite3

from test_migration_0020 import _alembic, _build_0019


def _state(con):
    patterns = dict(con.execute("SELECT code, value_pattern FROM kyb_document_types WHERE country = 'IN'").fetchall())
    [active] = con.execute("SELECT active FROM country_document_rules WHERE country = 'IN'").fetchone()
    return patterns, bool(active)


def test_0040_switches_off_the_seeded_india_checks(tmp_path):
    db = tmp_path / "v39.db"
    _build_0019(db)
    assert _alembic(db, "upgrade", "0039_samples").returncode == 0
    con = sqlite3.connect(db)
    con.execute("UPDATE kyb_document_types SET value_pattern = '[0-9]{14}X' WHERE country = 'IN' AND code = 'fssai'")
    con.commit()
    patterns, active = _state(con)
    assert patterns["gstin"] and patterns["pan"] and active
    con.close()

    proc = _alembic(db, "upgrade", "0040_no_builtin_india_checks")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    patterns, active = _state(con)
    assert (patterns["gstin"], patterns["pan"], active) == (None, None, False)
    assert patterns["fssai"] == "[0-9]{14}X"  # not the seeded GSTIN/PAN: untouched
    con.close()

    assert _alembic(db, "downgrade", "0039_samples").returncode == 0
    con = sqlite3.connect(db)
    patterns, active = _state(con)
    assert patterns["pan"] == "[A-Z]{5}[0-9]{4}[A-Z]" and active
    con.close()
