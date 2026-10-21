"""0019_business_entity data mapping on a 0018-shaped SQLite database.

Builds the exact 0018 schema (frozen DDL from the SQLite dev DB), inserts
sample rows — including a passwordless account, 3-letter country codes, a
country name and dirty values the new CHECKs would reject — runs
``alembic upgrade head`` in a subprocess and asserts the result.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent

SCHEMA_0018 = """
CREATE TABLE admin_actions (
	id CHAR(32) NOT NULL, 
	admin_email VARCHAR(200) NOT NULL, 
	action VARCHAR(50) NOT NULL, 
	target_type VARCHAR(30) NOT NULL, 
	target_id VARCHAR(64) NOT NULL, 
	reason VARCHAR(500), 
	details JSON, 
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_admin_actions_created_at ON admin_actions (created_at);
CREATE INDEX ix_admin_actions_target ON admin_actions (target_type, target_id);
CREATE TABLE users (
	id CHAR(32) NOT NULL, 
	email VARCHAR(200) NOT NULL, 
	business_name VARCHAR(200), 
	password_hash VARCHAR(255), 
	must_change_password BOOLEAN DEFAULT 'false' NOT NULL, 
	session_version INTEGER DEFAULT '0' NOT NULL, 
	email_verified_at DATETIME, 
	status VARCHAR(20) NOT NULL, 
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	verification_submitted_at DATETIME, 
	verified_at DATETIME, 
	verification_rejected_reason VARCHAR(500), 
	deleted_at DATETIME, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_users_email ON users (email);
CREATE TABLE business_profiles (
	id CHAR(32) NOT NULL, 
	user_id CHAR(32) NOT NULL, 
	legal_name VARCHAR(200), 
	industry VARCHAR(120), 
	operating_countries JSON, 
	website_url VARCHAR(300), 
	legal_name_normalized VARCHAR(200), 
	website_normalized VARCHAR(300), 
	trade_position VARCHAR(40), 
	seller_type VARCHAR(60), 
	business_role VARCHAR(60), 
	export_status VARCHAR(40), 
	target_markets JSON, 
	target_buyer_types JSON, 
	main_objective VARCHAR(200), 
	company_introduction TEXT, 
	business_type VARCHAR(100), 
	nature_of_business VARCHAR(200), 
	udyam VARCHAR(20), 
	bank_account_number VARCHAR(30), 
	bank_ifsc VARCHAR(11), 
	bank_holder_name VARCHAR(100), 
	bank_branch_name VARCHAR(200), 
	bank_name VARCHAR(100), 
	ifsc_verified_at DATETIME, 
	onboarded_at DATETIME, 
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX uq_business_profiles_website_normalized ON business_profiles (website_normalized);
CREATE UNIQUE INDEX uq_business_profiles_legal_name_normalized ON business_profiles (legal_name_normalized);
CREATE TABLE products (
	id CHAR(32) NOT NULL, 
	user_id CHAR(32) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	category VARCHAR(50) NOT NULL, 
	variety VARCHAR(100), 
	origin_state VARCHAR(100), 
	packaging VARCHAR(50), 
	quantity NUMERIC(12, 2), 
	unit VARCHAR(10) DEFAULT 'MT' NOT NULL, 
	moq NUMERIC(12, 2), 
	price_per_unit NUMERIC(12, 2), 
	description TEXT, 
	photos JSON NOT NULL, 
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_products_user_id ON products (user_id);
CREATE TABLE profiles (
	id CHAR(32) NOT NULL, 
	user_id CHAR(32) NOT NULL, 
	full_name VARCHAR(100) NOT NULL, 
	phone VARCHAR(20), 
	phone_normalized VARCHAR(20), 
	department VARCHAR(80), 
	position VARCHAR(120), 
	address_line VARCHAR(200), 
	city VARCHAR(100), 
	state VARCHAR(100), 
	pincode CHAR(6), 
	country VARCHAR(100) DEFAULT 'India' NOT NULL, 
	website_url VARCHAR(300), 
	google_business_url VARCHAR(300), 
	facebook_url VARCHAR(300), 
	consent_at DATETIME, 
	consent_version VARCHAR(30), 
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (user_id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX uq_profiles_phone_normalized ON profiles (phone_normalized);
CREATE TABLE temp_credentials (
	id CHAR(32) NOT NULL, 
	user_id CHAR(32) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	expires_at DATETIME NOT NULL, 
	attempt_count INTEGER NOT NULL, 
	consumed_at DATETIME, 
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX ix_temp_credentials_user_id ON temp_credentials (user_id);
CREATE TABLE verification_docs (
	id CHAR(32) NOT NULL, 
	user_id CHAR(32) NOT NULL, 
	cert_type VARCHAR(150) NOT NULL, 
	filename VARCHAR(300) NOT NULL, 
	stored_path VARCHAR(400) NOT NULL, 
	mime_type VARCHAR(120) NOT NULL, 
	size_bytes INTEGER NOT NULL, 
	status VARCHAR(8) NOT NULL, 
	rejection_reason VARCHAR(500), 
	reviewed_at DATETIME, 
	uploaded_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX ix_verification_docs_user_id ON verification_docs (user_id);
CREATE TABLE contact_reveals (
	id CHAR(32) NOT NULL, 
	buyer_id CHAR(32) NOT NULL, 
	seller_id CHAR(32) NOT NULL, 
	product_id CHAR(32) NOT NULL, 
	revealed_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_reveals_buyer_product UNIQUE (buyer_id, product_id), 
	FOREIGN KEY(buyer_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(seller_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE
);
CREATE INDEX ix_contact_reveals_product_id ON contact_reveals (product_id);
CREATE INDEX ix_contact_reveals_buyer_id ON contact_reveals (buyer_id);
CREATE INDEX ix_contact_reveals_seller_id ON contact_reveals (seller_id);
CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL, 
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
"""


def _id() -> str:
    return uuid.uuid4().hex


def _build_0018(path: Path) -> dict:
    con = sqlite3.connect(path)
    con.executescript(SCHEMA_0018)
    con.execute("INSERT INTO alembic_version VALUES ('0018_hardening')")
    ids = {k: _id() for k in ("seller", "buyer", "ghost", "plain", "rej")}
    users = [
        # id, email, status, password_hash, verified_at, submitted, verified, reason
        (ids["seller"], "Seller@Kaveri.in", "verified", "h", "2026-01-01 00:00:00", None, "2026-01-03 00:00:00", None),
        (ids["buyer"], "buyer@mill.in", "pending_verification", "h", "2026-01-01 00:00:00", "2026-01-04 00:00:00", None, None),
        (ids["ghost"], "ghost@temp.in", "email_verified", None, None, None, None, None),
        (ids["plain"], "plain@nobiz.in", "active", "h", None, None, None, None),
        (ids["rej"], "rej@co.in", "rejected", "h", "2026-01-01 00:00:00", "2026-01-02 00:00:00", None, None),
    ]
    for uid, email, status, pw, ev, sub, ver, reason in users:
        con.execute(
            "INSERT INTO users (id, email, business_name, password_hash, must_change_password, session_version,"
            " email_verified_at, status, created_at, updated_at, verification_submitted_at, verified_at,"
            " verification_rejected_reason) VALUES (?,?,?,?,0,0,?,?,'2026-01-01 00:00:00','2026-01-05 00:00:00',?,?,?)",
            (uid, email, "Trading " + email, pw, ev, status, sub, ver, reason),
        )
    profiles = [
        (ids["seller"], "Ramesh Kumar", "+91 90000 00001", "Director", "Karnal", "Haryana", "132001", "India",
         "https://kaveri.in", "https://g.page/kaveri", "https://facebook.com/kaveri", "Sales"),
        (ids["buyer"], "Fatima Ali", "+971 50 000 0001", "Buyer", "Dubai", None, None, "United Arab Emirates",
         "https://mill.in", None, None, None),
        (ids["ghost"], "Ghost User", "+91 90000 00009", None, None, None, None, "India", None, None, None, None),
        (ids["rej"], "Rita", None, None, None, None, None, "Atlantis", None, None, None, None),
    ]
    for uid, name, phone, pos, city, state, pin, country, web, gb, fb, dept in profiles:
        con.execute(
            "INSERT INTO profiles (id, user_id, full_name, phone, phone_normalized, department, position, city, state,"
            " pincode, country, website_url, google_business_url, facebook_url, consent_at, consent_version)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,'2026-01-01 00:00:00','v1')",
            (_id(), uid, name, phone, "".join(c for c in phone if c.isdigit() or c == "+") if phone else None,
             dept, pos, city, state, pin, country, web, gb, fb),
        )
    biz = {
        "seller": _id(),
        "buyer": _id(),
        "ghost": _id(),
        "rej": _id(),
    }
    rows = [
        (biz["seller"], ids["seller"], "Kaveri Foods Pvt Ltd", "kaveri foods pvt ltd", '["IND", "ARE", "XYZ"]', None, None,
         "seller", '["SAU"]', "Rice"),
        (biz["buyer"], ids["buyer"], "Mill Trading LLC", "mill trading llc", '["ARE"]', None, None, "buyer", None, None),
        (biz["ghost"], ids["ghost"], "Ghost Co", "ghost co", '["IND"]', None, None, None, None, None),
        (biz["rej"], ids["rej"], "Rej Co", "rej co", '["IN"]', "rej.co", "rej.co", "both", None, None),
    ]
    for bid, uid, legal, legal_n, ops, web, web_n, tp, tm, industry in rows:
        con.execute(
            "INSERT INTO business_profiles (id, user_id, legal_name, legal_name_normalized, industry,"
            " operating_countries, website_url, website_normalized, trade_position, target_markets,"
            " target_buyer_types, main_objective, bank_account_number, udyam)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,'[\"importer\"]','grow','123456789','UDYAM-X')",
            (bid, uid, legal, legal_n, industry, ops, web, web_n, tp, tm),
        )
    prod = {k: _id() for k in ("good", "dirty", "ghost")}
    products = [
        (prod["good"], ids["seller"], "1121 Basmati", "Rice", "MT", "500", "25", "72.5"),
        (prod["dirty"], ids["seller"], "Mystery", "Gold", "tons", "-5", "10", "-1"),
        (prod["ghost"], ids["ghost"], "Ghost lot", "Rice", "MT", "1", "1", "1"),
    ]
    for pid, uid, name, cat, unit, qty, moq, price in products:
        con.execute(
            "INSERT INTO products (id, user_id, name, category, unit, quantity, moq, price_per_unit, photos)"
            " VALUES (?,?,?,?,?,?,?,?,'[\"/uploads/products/x.png\"]')",
            (pid, uid, name, cat, unit, qty, moq, price),
        )
    docs = {k: _id() for k in ("ok", "rej", "ghost")}
    for did, uid, status, reason in (
        (docs["ok"], ids["seller"], "approved", None),
        (docs["rej"], ids["seller"], "rejected", None),
        (docs["ghost"], ids["ghost"], "pending", None),
    ):
        con.execute(
            "INSERT INTO verification_docs (id, user_id, cert_type, filename, stored_path, mime_type, size_bytes,"
            " status, rejection_reason) VALUES (?,?,'GST Certificate','gst.pdf',?,'application/pdf',100,?,?)",
            (did, uid, f"{uid}/abc.pdf", status, reason),
        )
    reveals = {k: _id() for k in ("ok", "ghost")}
    con.execute(
        "INSERT INTO contact_reveals (id, buyer_id, seller_id, product_id) VALUES (?,?,?,?)",
        (reveals["ok"], ids["buyer"], ids["seller"], prod["good"]),
    )
    con.execute(
        "INSERT INTO contact_reveals (id, buyer_id, seller_id, product_id) VALUES (?,?,?,?)",
        (reveals["ghost"], ids["ghost"], ids["seller"], prod["good"]),
    )
    con.execute(
        "INSERT INTO temp_credentials (id, user_id, password_hash, expires_at, attempt_count) VALUES (?,?,'x','2026-01-02',0)",
        (_id(), ids["ghost"]),
    )
    con.commit()
    con.close()
    return {"users": ids, "biz": biz, "prod": prod, "docs": docs, "reveals": reveals}


def _upgrade(path: Path, target: str = "0019_business_entity") -> subprocess.CompletedProcess:
    env = dict(os.environ, DATABASE_URL=f"sqlite+aiosqlite:///{path}")
    return subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", target], cwd=BACKEND, env=env, capture_output=True, text=True
    )


def test_0019_maps_0018_data(tmp_path):
    db = tmp_path / "legacy.db"
    ids = _build_0018(db)
    proc = _upgrade(db)
    assert proc.returncode == 0, proc.stderr
    log = proc.stderr
    assert "deleted 1 account(s) that never set a password" in log
    assert "fixed" in log  # every data fix is logged

    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    q = lambda sql, *a: con.execute(sql, a).fetchall()  # noqa: E731
    u, b, p = ids["users"], ids["biz"], ids["prod"]

    assert q("SELECT version_num FROM alembic_version")[0][0] == "0019_business_entity"
    tables = {r[0] for r in q("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"profiles", "business_profiles", "temp_credentials", "verification_docs"}.isdisjoint(tables)
    assert {"businesses", "email_codes", "business_documents"} <= tables

    # Passwordless account and all of its data are gone.
    assert q("SELECT count(*) FROM users WHERE id = ?", u["ghost"])[0][0] == 0
    assert q("SELECT count(*) FROM businesses WHERE id = ?", b["ghost"])[0][0] == 0
    assert q("SELECT count(*) FROM products WHERE id = ?", p["ghost"])[0][0] == 0
    assert q("SELECT count(*) FROM business_documents WHERE id = ?", ids["docs"]["ghost"])[0][0] == 0
    assert q("SELECT count(*) FROM contact_reveals WHERE id = ?", ids["reveals"]["ghost"])[0][0] == 0

    # Every remaining user owns exactly one business.
    users = {r["id"]: r for r in q("SELECT * FROM users")}
    assert set(users) == {u["seller"], u["buyer"], u["plain"], u["rej"]}
    assert {r["role"] for r in users.values()} == {"owner"}
    assert {r["account_status"] for r in users.values()} == {"active"}
    assert len({r["business_id"] for r in users.values()}) == 4

    seller = users[u["seller"]]
    assert seller["business_id"] == b["seller"]  # business_profiles ids kept
    assert seller["email"] == "seller@kaveri.in"  # lowercased
    assert (seller["full_name"], seller["position"], seller["phone"], seller["phone_normalized"]) == (
        "Ramesh Kumar", "Director", "+91 90000 00001", "+919000000001"
    )
    assert seller["consent_version"] == "v1" and seller["consent_at"]
    plain = users[u["plain"]]
    assert plain["full_name"] == "plain"  # no profile → email local part
    assert plain["email_verified_at"]  # backfilled from created_at
    columns = {r[1] for r in q("PRAGMA table_info(users)")}
    assert {"status", "business_name", "must_change_password", "verified_at"}.isdisjoint(columns)

    biz = {r["id"]: r for r in q("SELECT * FROM businesses")}
    s = biz[b["seller"]]
    assert s["legal_name"] == "Kaveri Foods Pvt Ltd" and s["industry"] == "Rice"
    assert json.loads(s["operating_countries"]) == ["IN", "AE"]  # alpha-3 → alpha-2, unknown dropped
    assert json.loads(s["target_markets"]) == ["SA"]
    assert (s["city"], s["state"], s["pincode"], s["country"]) == ("Karnal", "Haryana", "132001", "IN")
    assert s["website_url"] == "https://kaveri.in" and s["website_normalized"] == "kaveri.in"  # from profile
    assert s["google_business_url"] == "https://g.page/kaveri" and s["facebook_url"] == "https://facebook.com/kaveri"
    assert s["verification_status"] == "verified" and s["verified_at"]
    assert s["verification_submitted_at"]  # was NULL → filled (CHECK)
    buyer = biz[b["buyer"]]
    assert buyer["verification_status"] == "pending_verification" and buyer["country"] == "AE"
    rej = biz[b["rej"]]
    assert rej["verification_status"] == "rejected" and rej["verification_rejected_reason"]  # placeholder
    assert rej["country"] == "IN"  # unknown country name → default
    assert rej["website_url"] == "rej.co"  # business value wins over profile
    plain_biz = biz[plain["business_id"]]
    assert plain_biz["verification_status"] == "draft" and plain_biz["legal_name"] is None
    bcols = {r[1] for r in q("PRAGMA table_info(businesses)")}
    assert {"main_objective", "udyam", "bank_account_number", "business_role", "onboarded_at"}.isdisjoint(bcols)

    prods = {r["id"]: r for r in q("SELECT * FROM products")}
    good, dirty = prods[p["good"]], prods[p["dirty"]]
    assert good["business_id"] == b["seller"] and good["created_by_user_id"] == u["seller"]
    assert good["currency"] == "INR" and good["deleted_at"] is None
    assert (dirty["category"], dirty["unit"], dirty["quantity"], dirty["price_per_unit"]) == ("Other", "MT", None, None)
    assert dirty["moq"] == 10  # quantity nulled, so moq stays

    docs = {r["id"]: r for r in q("SELECT * FROM business_documents")}
    ok = docs[ids["docs"]["ok"]]
    assert ok["business_id"] == b["seller"] and ok["uploaded_by_user_id"] == u["seller"]
    assert ok["doc_type"] == "GST Certificate" and ok["original_filename"] == "gst.pdf"
    assert ok["storage_key"] == f"verification/{u['seller']}/abc.pdf"
    assert docs[ids["docs"]["rej"]]["rejection_reason"]  # placeholder for the CHECK

    [reveal] = q("SELECT * FROM contact_reveals")
    assert reveal["buyer_business_id"] == b["buyer"] and reveal["seller_business_id"] == b["seller"]
    assert reveal["revealed_by_user_id"] == u["buyer"] and reveal["product_id"] == p["good"]

    names = {r[0] for r in q("SELECT name FROM sqlite_master WHERE type='index'")}
    assert {"uq_users_one_owner_per_business", "ix_products_market", "ix_admin_actions_admin"} <= names
    con.close()


def test_0019_downgrade_is_one_way(tmp_path):
    db = tmp_path / "legacy.db"
    _build_0018(db)
    assert _upgrade(db).returncode == 0
    env = dict(os.environ, DATABASE_URL=f"sqlite+aiosqlite:///{db}")
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "0018_hardening"],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0 and "one-way" in proc.stderr
