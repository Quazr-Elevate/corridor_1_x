"""0021_kyb_profile on a 0020-shaped SQLite database: seeded document types,
existing documents kept as "Other", the new content / completeness checks,
the no-Aadhaar rule, partial unique indexes, and a clean downgrade."""
from __future__ import annotations

import sqlite3
import uuid

import pytest
from test_migration_0020 import _alembic, _build_0019

_VAL = ("'ct'", "1", f"'{'a' * 64}'", "'1Z5'")  # encrypted, key version, hash, last4


def _doc_insert(con, biz, *, type_id=None, value=True, file=False, unique=False, status="pending", name="GSTIN"):
    cols = ["id", "business_id", "doc_type", "status", "value_unique"]
    vals = [f"'{uuid.uuid4().hex}'", f"'{biz}'", f"'{name}'", f"'{status}'", "1" if unique else "0"]
    if status == "rejected":
        cols.append("rejection_reason")
        vals.append("'wrong'")
    if type_id:
        cols.append("document_type_id")
        vals.append(f"'{type_id}'")
    if value:
        cols += ["value_encrypted", "value_key_version", "value_hash", "value_last4"]
        vals += list(_VAL)
    if file:
        cols += ["original_filename", "storage_key", "mime_type", "size_bytes"]
        vals += ["'a.pdf'", "'verification/x/a.pdf'", "'application/pdf'", "100"]
    con.execute(f"INSERT INTO business_documents ({', '.join(cols)}) VALUES ({', '.join(vals)})")


def test_0021_on_0020_db(tmp_path):
    db = tmp_path / "v20.db"
    ids = _build_0019(db)
    assert _alembic(db, "upgrade", "0020_exchange_rates").returncode == 0
    biz = ids["biz"]["seller"]
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO business_documents (id, business_id, doc_type, original_filename, storage_key, mime_type,"
        " size_bytes) VALUES (?, ?, 'GST Certificate', 'gst.pdf', 'verification/x/gst.pdf', 'application/pdf', 2048)",
        (uuid.uuid4().hex, biz),
    )
    con.commit()
    con.close()

    proc = _alembic(db, "upgrade", "head")
    assert proc.returncode == 0, proc.stderr

    con = sqlite3.connect(db)
    q = lambda sql, *a: con.execute(sql, a).fetchall()  # noqa: E731
    assert q("SELECT version_num FROM alembic_version")[0][0] == "0021_kyb_profile"

    # Seed: India + UAE, mandatory flags, no Aadhaar.
    seeded = {(c, code): mand for c, code, mand in q("SELECT country, code, is_mandatory FROM kyb_document_types")}
    assert seeded[("IN", "gstin")] == 1 and seeded[("IN", "pan")] == 1 and seeded[("AE", "trade_licence")] == 1
    assert seeded[("IN", "iec")] == 0
    assert len(seeded) == 7
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO kyb_document_types (id, country, code, name, input_kind) VALUES (?, 'IN', 'aadhaar', 'A', 'value')",
            (uuid.uuid4().hex,),
        )

    # Existing document survives as "Other" (no type, no value).
    old = q("SELECT doc_type, document_type_id, value_encrypted, storage_key FROM business_documents")
    assert ("GST Certificate", None, None, "verification/x/gst.pdf") in old
    assert all(r[1] is None and r[2] is None and r[3] for r in old)
    n_files = len(old)

    gstin = q("SELECT id FROM kyb_document_types WHERE code = 'gstin'")[0][0]
    other_biz = ids["biz"]["buyer"]

    # Value-only entry is fine; an entry with neither value nor file is not.
    _doc_insert(con, biz, type_id=gstin, unique=True)
    with pytest.raises(sqlite3.IntegrityError, match="has_content"):
        _doc_insert(con, biz, value=False, file=False, name="Other thing")
    # Half a value / half a file is rejected.
    with pytest.raises(sqlite3.IntegrityError, match="value_complete"):
        con.execute(
            "INSERT INTO business_documents (id, business_id, doc_type, value_encrypted) VALUES (?, ?, 'X', 'ct')",
            (uuid.uuid4().hex, biz),
        )
    with pytest.raises(sqlite3.IntegrityError, match="file_complete"):
        con.execute(
            "INSERT INTO business_documents (id, business_id, doc_type, storage_key) VALUES (?, ?, 'X', 'k')",
            (uuid.uuid4().hex, biz),
        )
    # One GSTIN entry per business…
    with pytest.raises(sqlite3.IntegrityError, match="business_documents"):
        _doc_insert(con, biz, type_id=gstin, unique=True)
    # …and the same GSTIN value can't belong to another business,
    with pytest.raises(sqlite3.IntegrityError, match="business_documents"):
        _doc_insert(con, other_biz, type_id=gstin, unique=True)
    # unless the other claim was rejected.
    _doc_insert(con, other_biz, type_id=gstin, unique=True, status="rejected")
    # "Other" entries may repeat.
    _doc_insert(con, biz, value=False, file=True, name="Spice Board")
    _doc_insert(con, biz, value=False, file=True, name="Spice Board")
    con.commit()

    assert {r[1] for r in q("PRAGMA table_info(businesses)")} >= {"logo_key", "banner_key"}
    assert "tour_completed_at" in {r[1] for r in q("PRAGMA table_info(users)")}
    con.close()

    # Downgrade drops value-only entries (the old table required a file).
    proc = _alembic(db, "downgrade", "0020_exchange_rates")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    assert con.execute("SELECT count(*) FROM business_documents WHERE storage_key IS NULL").fetchone()[0] == 0
    assert con.execute("SELECT count(*) FROM business_documents").fetchone()[0] == n_files + 2
    assert "kyb_document_types" not in {r[0] for r in con.execute("SELECT name FROM sqlite_master")}
    con.close()
