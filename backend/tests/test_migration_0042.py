"""0042_deal_documents on a 0041 database: templates, documents and
signatures arrive with their triggers, and go on downgrade."""
from __future__ import annotations

import sqlite3

import pytest
from test_migration_0020 import _alembic, _build_0019

DOC = (
    "INSERT INTO deal_documents (id, deal_id, kind, side, term_sheet_id, template_id, status, body, content_sha256, "
    "terms, value_minor, currency, expires_at, issued_at, updated_at) VALUES ('d', 'x', 'loi', 'buyer', 't', 'tpl', "
    "'issued', 'Text', ?, '{}', 100, 'INR', '2027-01-01', '2026-01-01', '2026-01-01')"
)


def test_0042_adds_frozen_documents_and_takes_them_back(tmp_path):
    db = tmp_path / "v41.db"
    _build_0019(db)
    assert _alembic(db, "upgrade", "0041_no_builtin_india_checks").returncode == 0
    proc = _alembic(db, "upgrade", "0042_deal_documents")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    con.execute("PRAGMA foreign_keys = OFF")
    con.execute(DOC, ("a" * 64,))
    con.execute("UPDATE deal_documents SET status = 'party_signed' WHERE id = 'd'")  # status moves
    with pytest.raises(sqlite3.IntegrityError, match="deal_document_frozen"):
        con.execute("UPDATE deal_documents SET body = 'Other' WHERE id = 'd'")
    con.execute(
        "INSERT INTO document_signatures (id, document_id, signer_type, user_id, signer_role, authority_confirmed, "
        "content_sha256, signed_at) VALUES ('s', 'd', 'party', 'u', 'Director', 1, ?, '2026-01-01')", ("a" * 64,)
    )
    with pytest.raises(sqlite3.IntegrityError, match="signature_insert_only"):
        con.execute("UPDATE document_signatures SET signer_role = 'X'")
    with pytest.raises(sqlite3.IntegrityError, match="ck_document_signatures_authority"):
        con.execute(
            "INSERT INTO document_signatures (id, document_id, signer_type, user_id, signer_role, authority_confirmed, "
            "content_sha256, signed_at) VALUES ('s2', 'e', 'party', 'u', 'Director', 0, ?, '2026-01-01')", ("a" * 64,)
        )
    con.commit()
    con.close()
    assert _alembic(db, "downgrade", "0041_no_builtin_india_checks").returncode == 0
    con = sqlite3.connect(db)
    left = con.execute("SELECT count(*) FROM sqlite_master WHERE name IN "
                       "('deal_documents', 'document_signatures', 'contract_templates')").fetchone()
    assert left == (0,)
    con.close()
