"""0027_identity_vault on a 0026-shaped SQLite database: live businesses get
a vault row with their values, a soft-deleted one gets none, verified
businesses get a company code, and the downgrade puts the columns back."""
from __future__ import annotations

import re
import sqlite3
import uuid

from test_migration_0020 import _alembic, _build_0019

INSERT = (
    "INSERT INTO businesses (id, country, verification_status, verification_submitted_at, verified_at, deleted_at,"
    " legal_name, legal_name_normalized, website_url, website_normalized, address_line, city, pincode, state)"
    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)
T = "2026-11-01 00:00:00"


def test_0027_moves_identity_and_issues_codes(tmp_path):
    db = tmp_path / "v26.db"
    _build_0019(db)
    assert _alembic(db, "upgrade", "0026_listing_review").returncode == 0
    verified, draft, gone = (uuid.uuid4().hex for _ in range(3))
    con = sqlite3.connect(db)
    before = con.execute("SELECT COUNT(*) FROM businesses WHERE deleted_at IS NULL").fetchone()[0]
    con.execute(INSERT, (verified, "AE", "verified", T, T, None, "Gulf Grain LLC", "gulf grain llc",
                         "https://gulfgrain.ae", "gulfgrain.ae", "Plot 4, JAFZA", "Dubai", None, "Dubai"))
    con.execute(INSERT, (draft, "IN", "draft", None, None, None, None, None, None, None, None, None, None, None))
    # Same name as the live one above: allowed before, because the row is deleted.
    con.execute(INSERT, (gone, "AE", "draft", None, None, T, "Gulf Grain LLC", "gulf grain llc",
                         None, None, "Old address", "Sharjah", None, None))
    con.commit()
    con.close()

    proc = _alembic(db, "upgrade", "0027_identity_vault")
    assert proc.returncode == 0, proc.stderr

    con = sqlite3.connect(db)
    columns = {r[1] for r in con.execute("PRAGMA table_info(businesses)")}
    assert "company_code" in columns and "state" in columns
    assert not columns & {"legal_name", "legal_name_normalized", "website_url", "address_line", "city", "pincode"}
    vault = {r[0]: r[1:] for r in con.execute(
        "SELECT business_id, legal_name, legal_name_normalized, website_normalized, address_line, city FROM business_identities"
    )}
    assert len(vault) == before + 2  # every live business, and not the deleted one
    assert vault[verified] == ("Gulf Grain LLC", "gulf grain llc", "gulfgrain.ae", "Plot 4, JAFZA", "Dubai")
    assert vault[draft] == (None, None, None, None, None)
    assert gone not in vault
    codes = dict(con.execute("SELECT id, company_code FROM businesses"))
    assert re.fullmatch(r"AE-\d{6}", codes[verified])
    assert codes[draft] is None and codes[gone] is None
    issued = [c for c in codes.values() if c]
    assert len(issued) == len(set(issued))
    try:
        con.execute("INSERT INTO business_identities (business_id, legal_name_normalized) VALUES (?, 'gulf grain llc')", (draft + "0",))
        raise AssertionError("a duplicate company name was accepted")
    except sqlite3.IntegrityError:
        pass
    con.close()

    proc = _alembic(db, "downgrade", "0026_listing_review")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    assert "business_identities" not in {r[0] for r in con.execute("SELECT name FROM sqlite_master")}
    row = con.execute("SELECT legal_name, city, website_normalized FROM businesses WHERE id = ?", (verified,)).fetchone()
    assert row == ("Gulf Grain LLC", "Dubai", "gulfgrain.ae")
    assert "company_code" not in {r[1] for r in con.execute("PRAGMA table_info(businesses)")}
    con.close()
