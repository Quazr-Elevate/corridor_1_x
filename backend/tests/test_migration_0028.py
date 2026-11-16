"""0028_credits on a 0027-shaped SQLite database: the credit tables arrive
with their placeholder prices and plans, and the downgrade removes them."""
from __future__ import annotations

import sqlite3

from test_migration_0020 import _alembic, _build_0019

TABLES = {
    "credit_wallets", "credit_ledger", "credit_free_quotas", "credit_prices", "credit_plans", "plan_purchases",
    "payment_events", "idempotency_keys",
}


def test_0028_creates_and_seeds_the_credit_tables(tmp_path):
    db = tmp_path / "v27.db"
    _build_0019(db)
    assert _alembic(db, "upgrade", "0027_identity_vault").returncode == 0
    proc = _alembic(db, "upgrade", "0028_credits")
    assert proc.returncode == 0, proc.stderr

    con = sqlite3.connect(db)
    assert TABLES <= {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    prices = dict(con.execute("SELECT action, credits FROM credit_prices WHERE is_placeholder"))
    assert prices == {"RFQ_POST": 5, "OFFER_UNLOCK": 2, "RFQ_VIEW": 1, "LISTING_BOOST": 10, "AI_QUERY": 1, "SAMPLE_FEE": 5}
    plans = list(con.execute("SELECT code, kind, credits, price_minor, currency, period_days FROM credit_plans ORDER BY sort_order"))
    assert plans == [
        ("starter", "plan", 50, 99900, "INR", 30),
        ("growth", "plan", 200, 349900, "INR", 30),
        ("topup-25", "top_up", 25, 59900, "INR", None),
    ]
    assert con.execute("SELECT COUNT(*) FROM credit_wallets").fetchone()[0] == 0  # created on first read, not here
    con.close()

    proc = _alembic(db, "downgrade", "0027_identity_vault")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    assert not TABLES & {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    con.close()
