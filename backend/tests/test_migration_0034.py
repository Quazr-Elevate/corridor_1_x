"""0034_credit_expiry_invoices on a 0033-shaped SQLite database: invoices
already issued move into the year they were paid, the counters continue
from them, and the downgrade puts the single numbering back."""
from __future__ import annotations

import sqlite3
import uuid

from test_migration_0020 import _alembic, _build_0019


def test_0034_moves_existing_invoices_into_their_financial_year(tmp_path):
    db = tmp_path / "v33.db"
    _build_0019(db)
    assert _alembic(db, "upgrade", "0033_country_rules").returncode == 0
    con = sqlite3.connect(db)
    business = uuid.uuid4().hex
    con.execute(
        "INSERT INTO businesses (id, country, verification_status, created_at, updated_at) "
        "VALUES (?, 'IN', 'draft', '2026-01-01', '2026-01-01')",
        (business,),
    )
    for number, paid in ((1, "2026-03-31 10:00:00"), (2, "2026-04-02 10:00:00")):
        con.execute(
            "INSERT INTO plan_purchases (id, business_id, plan_code, plan_kind, credits, amount_minor, currency, status, "
            "provider, provider_order_id, invoice_number, created_at, paid_at) "
            "VALUES (?, ?, 'topup-25', 'top_up', 25, 59900, 'INR', 'paid', 'test', ?, ?, ?, ?)",
            (uuid.uuid4().hex, business, f"order_{number}", number, paid, paid),
        )
    con.commit()
    con.close()

    proc = _alembic(db, "upgrade", "0034_credit_expiry_invoices")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    assert con.execute("SELECT invoice_number, invoice_fy FROM plan_purchases ORDER BY invoice_number").fetchall() == [
        (1, "2025-26"), (2, "2026-27"),
    ]
    assert dict(con.execute("SELECT fy, last_number FROM invoice_counters")) == {"2025-26": 1, "2026-27": 2}
    assert "plan_credits" in {r[1] for r in con.execute("PRAGMA table_info(credit_wallets)")}
    assert "EXPIRY" in con.execute("SELECT sql FROM sqlite_master WHERE name = 'credit_ledger'").fetchone()[0]
    con.close()

    proc = _alembic(db, "downgrade", "0033_country_rules")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    assert "invoice_fy" not in {r[1] for r in con.execute("PRAGMA table_info(plan_purchases)")}
    assert "EXPIRY" not in con.execute("SELECT sql FROM sqlite_master WHERE name = 'credit_ledger'").fetchone()[0]
    con.close()
