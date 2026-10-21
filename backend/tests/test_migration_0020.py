"""0020_exchange_rates on a 0019-shaped SQLite database: bootstrap rates,
price_usd backfill, display_currency from the business country, the new
CHECKs / indexes, and a clean downgrade."""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import uuid

from test_migration_0019 import BACKEND, _build_0018, _upgrade


def _alembic(db, *args) -> subprocess.CompletedProcess:
    env = dict(os.environ, DATABASE_URL=f"sqlite+aiosqlite:///{db}")
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=BACKEND, env=env, capture_output=True, text=True)


def _build_0019(path) -> dict:
    ids = _build_0018(path)
    proc = _upgrade(path, "0019_business_entity")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(path)
    seller_biz, seller = ids["biz"]["seller"], ids["users"]["seller"]
    # A Saudi business → USD display currency.
    sa_biz, sa_user = uuid.uuid4().hex, uuid.uuid4().hex
    con.execute("INSERT INTO businesses (id, country, verification_status) VALUES (?, 'SA', 'draft')", (sa_biz,))
    con.execute(
        "INSERT INTO users (id, business_id, email, password_hash, email_verified_at, full_name)"
        " VALUES (?, ?, 'ksa@grain.sa', 'h', '2026-01-01 00:00:00', 'Omar')",
        (sa_user, sa_biz),
    )
    extra = {k: uuid.uuid4().hex for k in ("aed", "usd", "deleted")}
    for key, currency, price, deleted in (
        ("aed", "AED", "367.25", None),
        ("usd", "USD", "480", None),
        ("deleted", "INR", "9500", "2026-02-01 00:00:00"),
    ):
        con.execute(
            "INSERT INTO products (id, business_id, created_by_user_id, name, category, unit, price_per_unit,"
            " currency, photos, deleted_at) VALUES (?,?,?,?,'Rice','MT',?,?,'[]',?)",
            (extra[key], seller_biz, seller, f"{key} lot", price, currency, deleted),
        )
    con.commit()
    con.close()
    ids["prod"].update(extra)
    ids["users"]["sa"] = sa_user
    return ids


def test_0020_on_0019_db(tmp_path):
    db = tmp_path / "v19.db"
    ids = _build_0019(db)
    proc = _alembic(db, "upgrade", "head")
    assert proc.returncode == 0, proc.stderr
    assert "0020: price_usd filled for 3 listing(s)" in proc.stderr

    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    q = lambda sql, *a: con.execute(sql, a).fetchall()  # noqa: E731
    assert q("SELECT version_num FROM alembic_version")[0][0] == "0020_exchange_rates"

    rates = {r["quote"]: r for r in q("SELECT * FROM exchange_rates")}
    assert set(rates) == {"INR", "AED"}
    assert (rates["INR"]["rate"], rates["INR"]["source"], rates["INR"]["base"]) == (95, "manual", "USD")
    assert (rates["AED"]["rate"], rates["AED"]["source"]) == (3.6725, "pegged")
    assert rates["INR"]["as_of"] == rates["AED"]["as_of"]

    p = {r["id"]: r for r in q("SELECT id, price_usd, price_usd_as_of, price_per_unit FROM products")}
    prod = ids["prod"]
    assert p[prod["good"]]["price_usd"] == 0.76  # ₹72.50 / 95
    assert p[prod["aed"]]["price_usd"] == 100  # AED 367.25 / 3.6725
    assert p[prod["usd"]]["price_usd"] == 480
    assert p[prod["good"]]["price_usd_as_of"] == rates["INR"]["as_of"]
    assert p[prod["dirty"]]["price_usd"] is None  # unpriced
    assert p[prod["deleted"]]["price_usd"] is None  # deleted listings are skipped

    users = {r["id"]: r["display_currency"] for r in q("SELECT id, display_currency FROM users")}
    u = ids["users"]
    assert users[u["seller"]] == "INR" and users[u["buyer"]] == "AED" and users[u["sa"]] == "USD"
    assert users[u["plain"]] == "INR"  # new draft business defaults to IN

    names = {r[0] for r in q("SELECT name FROM sqlite_master WHERE type='index'")}
    assert {"ix_exchange_rates_latest", "ix_products_market_price", "ix_products_market", "uq_users_email"} <= names
    ddl = " ".join(r[0] for r in q("SELECT sql FROM sqlite_master WHERE name IN ('products', 'users', 'exchange_rates')"))
    for name in (
        "uq_exchange_rates_quote_day", "ck_exchange_rates_rate_positive", "ck_exchange_rates_codes",
        "ck_products_price_usd", "ck_users_display_currency",
        "ck_products_amounts", "ck_users_email_lowercase",  # 0019 CHECKs survive the batch rebuild
    ):
        assert name in ddl, name

    for sql in (
        "UPDATE users SET display_currency = 'EUR'",
        "UPDATE products SET price_usd = -1",
        "INSERT INTO exchange_rates (id, base, quote, rate, as_of, source) VALUES ('x', 'USD', 'INR', 0, '2026-01-01', 'manual')",
    ):
        try:
            con.execute(sql)
        except sqlite3.IntegrityError:
            continue
        raise AssertionError(f"accepted: {sql}")
    con.close()

    proc = _alembic(db, "downgrade", "0019_business_entity")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    assert not con.execute("SELECT name FROM sqlite_master WHERE name = 'exchange_rates'").fetchall()
    cols = {r[1] for r in con.execute("PRAGMA table_info(users)")} | {r[1] for r in con.execute("PRAGMA table_info(products)")}
    assert {"display_currency", "price_usd", "price_usd_as_of"}.isdisjoint(cols)
    con.close()
