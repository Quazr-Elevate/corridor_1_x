"""countries table; FKs from businesses.country and kyb_document_types.country

Revision ID: 0023_countries
Revises: 0022_reject_items
Create Date: 2026-10-31

Implements docs/04_data_model.md → "Countries (0023)":

* new table ``countries`` (code PK, name, flag, dial code, default currency,
  address labels, optional postcode pattern, active, created/updated by/at);
* seeded with India and the UAE, plus **every code already used** by
  ``businesses.country`` or ``kyb_document_types.country`` (from a frozen
  reference of 20 countries; unknown codes get their code as the name and
  are created paused), so the new foreign keys never fail on existing data;
* ``fk_businesses_country`` and ``fk_kyb_document_types_country``
  (ON DELETE RESTRICT — countries are paused, never deleted).

Portable (Postgres + SQLite batch ops). Reversible.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023_countries"
down_revision: Union[str, None] = "0022_reject_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Frozen copy (migrations must not import app code).
# code: (name, flag, dial, currency, region label, postal label, postal pattern)
REFERENCE = {
    "IN": ("India", "🇮🇳", "+91", "INR", "State", "PIN code", r"[1-9][0-9]{5}"),
    "AE": ("United Arab Emirates", "🇦🇪", "+971", "AED", "Emirate", "PO Box", None),
    "SA": ("Saudi Arabia", "🇸🇦", "+966", "USD", "Province", "Postal code", r"[0-9]{5}"),
    "OM": ("Oman", "🇴🇲", "+968", "USD", "Governorate", "Postal code", r"[0-9]{3}"),
    "QA": ("Qatar", "🇶🇦", "+974", "USD", "Municipality", "PO Box", None),
    "KW": ("Kuwait", "🇰🇼", "+965", "USD", "Governorate", "Postal code", r"[0-9]{5}"),
    "BH": ("Bahrain", "🇧🇭", "+973", "USD", "Governorate", "Postal code", r"[0-9]{3,4}"),
    "US": ("United States", "🇺🇸", "+1", "USD", "State", "ZIP code", r"[0-9]{5}(-[0-9]{4})?"),
    "GB": ("United Kingdom", "🇬🇧", "+44", "USD", "County", "Postcode", None),
    "DE": ("Germany", "🇩🇪", "+49", "USD", "State", "Postal code", r"[0-9]{5}"),
    "NL": ("Netherlands", "🇳🇱", "+31", "USD", "Province", "Postal code", r"[0-9]{4}\s?[A-Z]{2}"),
    "SG": ("Singapore", "🇸🇬", "+65", "USD", "Region", "Postal code", r"[0-9]{6}"),
    "MY": ("Malaysia", "🇲🇾", "+60", "USD", "State", "Postcode", r"[0-9]{5}"),
    "ID": ("Indonesia", "🇮🇩", "+62", "USD", "Province", "Postal code", r"[0-9]{5}"),
    "TH": ("Thailand", "🇹🇭", "+66", "USD", "Province", "Postal code", r"[0-9]{5}"),
    "VN": ("Vietnam", "🇻🇳", "+84", "USD", "Province", "Postal code", r"[0-9]{6}"),
    "JP": ("Japan", "🇯🇵", "+81", "USD", "Prefecture", "Postal code", r"[0-9]{3}-?[0-9]{4}"),
    "CN": ("China", "🇨🇳", "+86", "USD", "Province", "Postal code", r"[0-9]{6}"),
    "KR": ("South Korea", "🇰🇷", "+82", "USD", "Province", "Postal code", r"[0-9]{5}"),
    "AU": ("Australia", "🇦🇺", "+61", "USD", "State", "Postcode", r"[0-9]{4}"),
}
ALWAYS = ("IN", "AE")
CURRENCIES = ("INR", "AED", "USD")


def upgrade() -> None:
    countries = op.create_table(
        "countries",
        sa.Column("code", sa.CHAR(2), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("flag", sa.String(8), nullable=True),
        sa.Column("dial_code", sa.String(6), nullable=True),
        sa.Column("default_currency", sa.CHAR(3), nullable=False, server_default="USD"),
        sa.Column("region_label", sa.String(30), nullable=False, server_default="State / region"),
        sa.Column("postal_label", sa.String(30), nullable=False, server_default="Postal code"),
        sa.Column("postal_pattern", sa.String(100), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("updated_by", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("length(code) = 2 AND code = upper(code)", name="ck_countries_code"),
        sa.CheckConstraint("length(trim(name)) >= 2", name="ck_countries_name"),
        sa.CheckConstraint("dial_code IS NULL OR dial_code LIKE '+%'", name="ck_countries_dial_code"),
        sa.CheckConstraint(
            "default_currency IN (" + ", ".join(f"'{c}'" for c in CURRENCIES) + ")",
            name="ck_countries_default_currency",
        ),
    )
    op.create_index("ix_countries_active", "countries", ["active"])
    op.create_index("uq_countries_name", "countries", ["name"], unique=True)

    # Seed: the defaults + every code already referenced (online only — the
    # offline SQL seeds just the defaults).
    codes = set(ALWAYS)
    if not op.get_context().as_sql:
        bind = op.get_bind()
        for table in ("businesses", "kyb_document_types"):
            codes |= {r[0].strip().upper() for r in bind.execute(sa.text(f"SELECT DISTINCT country FROM {table}")) if r[0]}
    rows = []
    for code in sorted(codes):
        if code in REFERENCE:
            name, flag, dial, cur, region, postal, pattern = REFERENCE[code]
            active = True
        else:  # unknown code in old data: keep it valid, paused, for an admin to complete
            name, flag, dial, cur, region, postal, pattern = (code, None, None, "USD", "State / region", "Postal code", None)
            active = False
        rows.append({
            "code": code, "name": name, "flag": flag, "dial_code": dial, "default_currency": cur,
            "region_label": region, "postal_label": postal, "postal_pattern": pattern, "active": active,
            "created_by": "system", "updated_by": "system",
        })
    op.bulk_insert(countries, rows)

    with op.batch_alter_table("businesses") as batch:
        batch.create_foreign_key("fk_businesses_country", "countries", ["country"], ["code"], ondelete="RESTRICT")
    with op.batch_alter_table("kyb_document_types") as batch:
        batch.create_foreign_key("fk_kyb_document_types_country", "countries", ["country"], ["code"], ondelete="RESTRICT")


def downgrade() -> None:
    with op.batch_alter_table("kyb_document_types") as batch:
        batch.drop_constraint("fk_kyb_document_types_country", type_="foreignkey")
    with op.batch_alter_table("businesses") as batch:
        batch.drop_constraint("fk_businesses_country", type_="foreignkey")
    op.drop_index("uq_countries_name", table_name="countries")
    op.drop_index("ix_countries_active", table_name="countries")
    op.drop_table("countries")
