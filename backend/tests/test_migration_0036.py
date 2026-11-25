"""0036_single_address on a 0035-shaped SQLite database: line, city and
pincode fold into one address (in reading order, blanks skipped), the two
columns and the countries' address labels are dropped, ``businesses.state``
is untouched, and the downgrade puts the columns back."""
from __future__ import annotations

import sqlite3
import uuid

from test_migration_0020 import _alembic, _build_0019

BIZ = "INSERT INTO businesses (id, country, verification_status, state) VALUES (?, ?, 'draft', ?)"
VAULT = "INSERT INTO business_identities (business_id, address_line, city, pincode) VALUES (?, ?, ?, ?)"


def test_0036_folds_the_address_into_one_field(tmp_path):
    db = tmp_path / "v35.db"
    _build_0019(db)
    assert _alembic(db, "upgrade", "0035_user_identity_vault").returncode == 0
    full, city_only, empty = (uuid.uuid4().hex for _ in range(3))
    con = sqlite3.connect(db)
    for bid, state, line, city, pin in (
        (full, "Haryana", "12 Mill Road", "Karnal", "132001"),
        (city_only, "Dubai", None, " Dubai ", None),
        (empty, None, None, None, None),
    ):
        con.execute(BIZ, (bid, "IN", state))
        con.execute(VAULT, (bid, line, city, pin))
    con.commit()
    con.close()

    proc = _alembic(db, "upgrade", "0036_single_address")
    assert proc.returncode == 0, proc.stderr

    con = sqlite3.connect(db)
    vault_cols = {r[1] for r in con.execute("PRAGMA table_info(business_identities)")}
    assert "address_line" in vault_cols and not vault_cols & {"city", "pincode"}
    country_cols = {r[1] for r in con.execute("PRAGMA table_info(countries)")}
    assert not country_cols & {"region_label", "postal_label", "postal_pattern"}
    address = dict(con.execute("SELECT business_id, address_line FROM business_identities"))
    assert address[full] == "12 Mill Road, Karnal, 132001"
    assert address[city_only] == "Dubai"
    assert address[empty] is None
    # The region the market shows stays where it was.
    assert dict(con.execute("SELECT id, state FROM businesses"))[full] == "Haryana"
    con.close()

    proc = _alembic(db, "downgrade", "0035_user_identity_vault")
    assert proc.returncode == 0, proc.stderr
    con = sqlite3.connect(db)
    assert {"city", "pincode"} <= {r[1] for r in con.execute("PRAGMA table_info(business_identities)")}
    labels = con.execute("SELECT region_label, postal_label FROM countries LIMIT 1").fetchone()
    assert labels in (None, ("State / region", "Postal code"))
    con.close()
