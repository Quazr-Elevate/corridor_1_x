"""business entity: businesses / users / email_codes / business_documents

Revision ID: 0019_business_entity
Revises: 0018_hardening
Create Date: 2026-10-17

Implements docs/04_data_model.md ("Migration from the current schema"):

* ``business_profiles`` → ``businesses`` (same ids; the per-user 1:1 link is
  dropped). Users without a business profile get a new ``draft`` business.
  Verification state moves from ``users`` to ``businesses``
  (verified / rejected / pending_verification kept, anything else → draft).
* ``profiles`` is merged away: full_name / phone / position / consent → users;
  address, city, state, pincode, country (→ ISO alpha-2),
  google_business_url, facebook_url → businesses; website_url → businesses
  only when the business has none. ``department`` is dropped.
* ``users`` gains business_id, role (owner), account_status (active) and the
  person fields; loses status, business_name, must_change_password and the
  verification columns. password_hash / email_verified_at / full_name become
  NOT NULL.
* ``verification_docs`` → ``business_documents`` (cert_type → doc_type,
  filename → original_filename, stored_path → storage_key with the
  ``verification/`` prefix, user_id → business_id + uploaded_by_user_id).
* ``products.user_id`` → business_id + created_by_user_id; new currency (INR)
  and deleted_at.
* ``contact_reveals`` buyer_id / seller_id → buyer_business_id +
  revealed_by_user_id / seller_business_id.
* ``temp_credentials`` dropped (replaced by ``email_codes``).
* 3-letter country codes in arrays → alpha-2.
* Indexes / UNIQUE / CHECK constraints per the spec's "Indexes and
  table-level constraints" section (partial uniques on live rows). Data is
  cleaned BEFORE the constraints are created, and every fix is logged:
  non-draft businesses without a submission date / verified without
  verified_at get updated_at, rejected without a reason get a placeholder
  reason (businesses and documents), emails are lowercased, products with an
  unknown category → 'Other', unknown unit → 'MT', negative amounts → NULL,
  moq > quantity → moq NULL, names shorter than 2 chars → "Untitled
  listing"; documents with an invalid size are dropped.
* **Accounts that never set a real password (password_hash NULL) are deleted
  with all their data** (profile, business profile, documents, products,
  reveals, temp credentials).

Portable (Postgres + SQLite via batch ops). Data moves are done in Python
and only run online; ``--sql`` (offline) renders the DDL only.

ONE-WAY: downgrade raises NotImplementedError — restore a backup instead.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019_business_entity"
down_revision: Union[str, None] = "0018_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

log = logging.getLogger("alembic.runtime.migration")

# ── Frozen helpers (migrations must not import app code) ─────────────

_WS = re.compile(r"\s+")
_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*://")


def _norm_phone(raw):
    if not raw:
        return None
    out = "".join(ch for ch in raw if ch.isdigit() or ch == "+")
    return out or None


def _norm_website(raw):
    if not raw:
        return None
    s = _SCHEME.sub("", raw.strip().lower())
    s = s.split("#", 1)[0].split("?", 1)[0]
    if s.startswith("www."):
        s = s[4:]
    s = s.rstrip("/")
    return s or None


# (alpha-2, alpha-3, English name) — frozen copy of app/shared/countries.py
_COUNTRIES = (
    ('AF', 'AFG', 'Afghanistan'), ('AX', 'ALA', 'Aland Islands'), ('AL', 'ALB', 'Albania'),
    ('DZ', 'DZA', 'Algeria'), ('AS', 'ASM', 'American Samoa'), ('AD', 'AND', 'Andorra'),
    ('AO', 'AGO', 'Angola'), ('AI', 'AIA', 'Anguilla'), ('AQ', 'ATA', 'Antarctica'),
    ('AG', 'ATG', 'Antigua and Barbuda'), ('AR', 'ARG', 'Argentina'), ('AM', 'ARM', 'Armenia'),
    ('AW', 'ABW', 'Aruba'), ('AU', 'AUS', 'Australia'), ('AT', 'AUT', 'Austria'),
    ('AZ', 'AZE', 'Azerbaijan'), ('BS', 'BHS', 'Bahamas'), ('BH', 'BHR', 'Bahrain'),
    ('BD', 'BGD', 'Bangladesh'), ('BB', 'BRB', 'Barbados'), ('BY', 'BLR', 'Belarus'),
    ('BE', 'BEL', 'Belgium'), ('BZ', 'BLZ', 'Belize'), ('BJ', 'BEN', 'Benin'),
    ('BM', 'BMU', 'Bermuda'), ('BT', 'BTN', 'Bhutan'), ('BO', 'BOL', 'Bolivia'),
    ('BQ', 'BES', 'Bonaire, Sint Eustatius and Saba'), ('BA', 'BIH', 'Bosnia and Herzegovina'), ('BW', 'BWA', 'Botswana'),
    ('BV', 'BVT', 'Bouvet Island'), ('BR', 'BRA', 'Brazil'), ('IO', 'IOT', 'British Indian Ocean Territory'),
    ('BN', 'BRN', 'Brunei Darussalam'), ('BG', 'BGR', 'Bulgaria'), ('BF', 'BFA', 'Burkina Faso'),
    ('BI', 'BDI', 'Burundi'), ('CV', 'CPV', 'Cabo Verde'), ('KH', 'KHM', 'Cambodia'),
    ('CM', 'CMR', 'Cameroon'), ('CA', 'CAN', 'Canada'), ('KY', 'CYM', 'Cayman Islands'),
    ('CF', 'CAF', 'Central African Republic'), ('TD', 'TCD', 'Chad'), ('CL', 'CHL', 'Chile'),
    ('CN', 'CHN', 'China'), ('CX', 'CXR', 'Christmas Island'), ('CC', 'CCK', 'Cocos (Keeling) Islands'),
    ('CO', 'COL', 'Colombia'), ('KM', 'COM', 'Comoros'), ('CG', 'COG', 'Congo'),
    ('CD', 'COD', 'Congo, Democratic Republic of the'), ('CK', 'COK', 'Cook Islands'), ('CR', 'CRI', 'Costa Rica'),
    ('CI', 'CIV', "Cote d'Ivoire"), ('HR', 'HRV', 'Croatia'), ('CU', 'CUB', 'Cuba'),
    ('CW', 'CUW', 'Curacao'), ('CY', 'CYP', 'Cyprus'), ('CZ', 'CZE', 'Czechia'),
    ('DK', 'DNK', 'Denmark'), ('DJ', 'DJI', 'Djibouti'), ('DM', 'DMA', 'Dominica'),
    ('DO', 'DOM', 'Dominican Republic'), ('EC', 'ECU', 'Ecuador'), ('EG', 'EGY', 'Egypt'),
    ('SV', 'SLV', 'El Salvador'), ('GQ', 'GNQ', 'Equatorial Guinea'), ('ER', 'ERI', 'Eritrea'),
    ('EE', 'EST', 'Estonia'), ('SZ', 'SWZ', 'Eswatini'), ('ET', 'ETH', 'Ethiopia'),
    ('FK', 'FLK', 'Falkland Islands'), ('FO', 'FRO', 'Faroe Islands'), ('FJ', 'FJI', 'Fiji'),
    ('FI', 'FIN', 'Finland'), ('FR', 'FRA', 'France'), ('GF', 'GUF', 'French Guiana'),
    ('PF', 'PYF', 'French Polynesia'), ('TF', 'ATF', 'French Southern Territories'), ('GA', 'GAB', 'Gabon'),
    ('GM', 'GMB', 'Gambia'), ('GE', 'GEO', 'Georgia'), ('DE', 'DEU', 'Germany'),
    ('GH', 'GHA', 'Ghana'), ('GI', 'GIB', 'Gibraltar'), ('GR', 'GRC', 'Greece'),
    ('GL', 'GRL', 'Greenland'), ('GD', 'GRD', 'Grenada'), ('GP', 'GLP', 'Guadeloupe'),
    ('GU', 'GUM', 'Guam'), ('GT', 'GTM', 'Guatemala'), ('GG', 'GGY', 'Guernsey'),
    ('GN', 'GIN', 'Guinea'), ('GW', 'GNB', 'Guinea-Bissau'), ('GY', 'GUY', 'Guyana'),
    ('HT', 'HTI', 'Haiti'), ('HM', 'HMD', 'Heard Island and McDonald Islands'), ('VA', 'VAT', 'Holy See'),
    ('HN', 'HND', 'Honduras'), ('HK', 'HKG', 'Hong Kong'), ('HU', 'HUN', 'Hungary'),
    ('IS', 'ISL', 'Iceland'), ('IN', 'IND', 'India'), ('ID', 'IDN', 'Indonesia'),
    ('IR', 'IRN', 'Iran'), ('IQ', 'IRQ', 'Iraq'), ('IE', 'IRL', 'Ireland'),
    ('IM', 'IMN', 'Isle of Man'), ('IL', 'ISR', 'Israel'), ('IT', 'ITA', 'Italy'),
    ('JM', 'JAM', 'Jamaica'), ('JP', 'JPN', 'Japan'), ('JE', 'JEY', 'Jersey'),
    ('JO', 'JOR', 'Jordan'), ('KZ', 'KAZ', 'Kazakhstan'), ('KE', 'KEN', 'Kenya'),
    ('KI', 'KIR', 'Kiribati'), ('KP', 'PRK', 'North Korea'), ('KR', 'KOR', 'South Korea'),
    ('KW', 'KWT', 'Kuwait'), ('KG', 'KGZ', 'Kyrgyzstan'), ('LA', 'LAO', 'Laos'),
    ('LV', 'LVA', 'Latvia'), ('LB', 'LBN', 'Lebanon'), ('LS', 'LSO', 'Lesotho'),
    ('LR', 'LBR', 'Liberia'), ('LY', 'LBY', 'Libya'), ('LI', 'LIE', 'Liechtenstein'),
    ('LT', 'LTU', 'Lithuania'), ('LU', 'LUX', 'Luxembourg'), ('MO', 'MAC', 'Macao'),
    ('MG', 'MDG', 'Madagascar'), ('MW', 'MWI', 'Malawi'), ('MY', 'MYS', 'Malaysia'),
    ('MV', 'MDV', 'Maldives'), ('ML', 'MLI', 'Mali'), ('MT', 'MLT', 'Malta'),
    ('MH', 'MHL', 'Marshall Islands'), ('MQ', 'MTQ', 'Martinique'), ('MR', 'MRT', 'Mauritania'),
    ('MU', 'MUS', 'Mauritius'), ('YT', 'MYT', 'Mayotte'), ('MX', 'MEX', 'Mexico'),
    ('FM', 'FSM', 'Micronesia'), ('MD', 'MDA', 'Moldova'), ('MC', 'MCO', 'Monaco'),
    ('MN', 'MNG', 'Mongolia'), ('ME', 'MNE', 'Montenegro'), ('MS', 'MSR', 'Montserrat'),
    ('MA', 'MAR', 'Morocco'), ('MZ', 'MOZ', 'Mozambique'), ('MM', 'MMR', 'Myanmar'),
    ('NA', 'NAM', 'Namibia'), ('NR', 'NRU', 'Nauru'), ('NP', 'NPL', 'Nepal'),
    ('NL', 'NLD', 'Netherlands'), ('NC', 'NCL', 'New Caledonia'), ('NZ', 'NZL', 'New Zealand'),
    ('NI', 'NIC', 'Nicaragua'), ('NE', 'NER', 'Niger'), ('NG', 'NGA', 'Nigeria'),
    ('NU', 'NIU', 'Niue'), ('NF', 'NFK', 'Norfolk Island'), ('MK', 'MKD', 'North Macedonia'),
    ('MP', 'MNP', 'Northern Mariana Islands'), ('NO', 'NOR', 'Norway'), ('OM', 'OMN', 'Oman'),
    ('PK', 'PAK', 'Pakistan'), ('PW', 'PLW', 'Palau'), ('PS', 'PSE', 'Palestine'),
    ('PA', 'PAN', 'Panama'), ('PG', 'PNG', 'Papua New Guinea'), ('PY', 'PRY', 'Paraguay'),
    ('PE', 'PER', 'Peru'), ('PH', 'PHL', 'Philippines'), ('PN', 'PCN', 'Pitcairn'),
    ('PL', 'POL', 'Poland'), ('PT', 'PRT', 'Portugal'), ('PR', 'PRI', 'Puerto Rico'),
    ('QA', 'QAT', 'Qatar'), ('RE', 'REU', 'Reunion'), ('RO', 'ROU', 'Romania'),
    ('RU', 'RUS', 'Russia'), ('RW', 'RWA', 'Rwanda'), ('BL', 'BLM', 'Saint Barthelemy'),
    ('SH', 'SHN', 'Saint Helena, Ascension and Tristan da Cunha'), ('KN', 'KNA', 'Saint Kitts and Nevis'), ('LC', 'LCA', 'Saint Lucia'),
    ('MF', 'MAF', 'Saint Martin (French part)'), ('PM', 'SPM', 'Saint Pierre and Miquelon'), ('VC', 'VCT', 'Saint Vincent and the Grenadines'),
    ('WS', 'WSM', 'Samoa'), ('SM', 'SMR', 'San Marino'), ('ST', 'STP', 'Sao Tome and Principe'),
    ('SA', 'SAU', 'Saudi Arabia'), ('SN', 'SEN', 'Senegal'), ('RS', 'SRB', 'Serbia'),
    ('SC', 'SYC', 'Seychelles'), ('SL', 'SLE', 'Sierra Leone'), ('SG', 'SGP', 'Singapore'),
    ('SX', 'SXM', 'Sint Maarten (Dutch part)'), ('SK', 'SVK', 'Slovakia'), ('SI', 'SVN', 'Slovenia'),
    ('SB', 'SLB', 'Solomon Islands'), ('SO', 'SOM', 'Somalia'), ('ZA', 'ZAF', 'South Africa'),
    ('GS', 'SGS', 'South Georgia and the South Sandwich Islands'), ('SS', 'SSD', 'South Sudan'), ('ES', 'ESP', 'Spain'),
    ('LK', 'LKA', 'Sri Lanka'), ('SD', 'SDN', 'Sudan'), ('SR', 'SUR', 'Suriname'),
    ('SJ', 'SJM', 'Svalbard and Jan Mayen'), ('SE', 'SWE', 'Sweden'), ('CH', 'CHE', 'Switzerland'),
    ('SY', 'SYR', 'Syria'), ('TW', 'TWN', 'Taiwan'), ('TJ', 'TJK', 'Tajikistan'),
    ('TZ', 'TZA', 'Tanzania'), ('TH', 'THA', 'Thailand'), ('TL', 'TLS', 'Timor-Leste'),
    ('TG', 'TGO', 'Togo'), ('TK', 'TKL', 'Tokelau'), ('TO', 'TON', 'Tonga'),
    ('TT', 'TTO', 'Trinidad and Tobago'), ('TN', 'TUN', 'Tunisia'), ('TR', 'TUR', 'Turkey'),
    ('TM', 'TKM', 'Turkmenistan'), ('TC', 'TCA', 'Turks and Caicos Islands'), ('TV', 'TUV', 'Tuvalu'),
    ('UG', 'UGA', 'Uganda'), ('UA', 'UKR', 'Ukraine'), ('AE', 'ARE', 'United Arab Emirates'),
    ('GB', 'GBR', 'United Kingdom'), ('US', 'USA', 'United States'), ('UM', 'UMI', 'United States Minor Outlying Islands'),
    ('UY', 'URY', 'Uruguay'), ('UZ', 'UZB', 'Uzbekistan'), ('VU', 'VUT', 'Vanuatu'),
    ('VE', 'VEN', 'Venezuela'), ('VN', 'VNM', 'Vietnam'), ('VG', 'VGB', 'Virgin Islands (British)'),
    ('VI', 'VIR', 'Virgin Islands (U.S.)'), ('WF', 'WLF', 'Wallis and Futuna'), ('EH', 'ESH', 'Western Sahara'),
    ('YE', 'YEM', 'Yemen'), ('ZM', 'ZMB', 'Zambia'), ('ZW', 'ZWE', 'Zimbabwe'),
)

_A2 = {a2 for a2, _, _ in _COUNTRIES}
_A3 = {a3: a2 for a2, a3, _ in _COUNTRIES}
_NAMES = {name.lower(): a2 for a2, _, name in _COUNTRIES} | {
    "uae": "AE", "u.a.e.": "AE", "emirates": "AE", "usa": "US", "u.s.a.": "US",
    "united states of america": "US", "uk": "GB", "u.k.": "GB", "great britain": "GB",
    "england": "GB", "bharat": "IN", "korea": "KR", "republic of korea": "KR",
    "russian federation": "RU", "viet nam": "VN", "turkiye": "TR", "czech republic": "CZ",
    "ivory coast": "CI", "holland": "NL", "the netherlands": "NL",
}


def _alpha2(value):
    if not value:
        return None
    v = str(value).strip()
    up = v.upper()
    if len(up) == 2 and up in _A2:
        return up
    if len(up) == 3 and up in _A3:
        return _A3[up]
    return _NAMES.get(v.lower())


def _alpha2_list(values):
    if values is None:
        return None
    out = []
    for raw in values:
        code = _alpha2(raw)
        if code is None:
            if raw:
                log.warning("0019: dropped unknown country code %r", raw)
            continue
        if code not in out:
            out.append(code)
    return out


TRADE_POSITIONS = {"seller", "buyer", "both"}
CATEGORIES = {"Rice", "Sugar", "Wheat", "Pulses", "Spices", "Oilseeds", "Cotton", "Millets", "Tea", "Coffee", "Other"}
UNITS = {"MT", "kg", "quintal"}
PLACEHOLDER_REASON = "Rejected before reasons were recorded — please review and resubmit."

# Partial "live rows only" index (portable).
_LIVE = {"sqlite_where": sa.text("deleted_at IS NULL"), "postgresql_where": sa.text("deleted_at IS NULL")}
STATUS_MAP = {
    "verified": "verified",
    "rejected": "rejected",
    "pending_verification": "pending_verification",
}

# ── Types ────────────────────────────────────────────────────────────

ENUMS = {
    "business_status": ("draft", "pending_verification", "verified", "rejected"),
    "user_role": ("owner", "admin", "member"),
    "account_status": ("active", "disabled"),
    "email_code_purpose": ("signup", "reset_password", "invite"),
    "doc_status": ("pending", "approved", "rejected"),  # exists since 0014
}


def _enum(name: str):
    values = ENUMS[name]
    return sa.Enum(*values, name=name).with_variant(
        postgresql.ENUM(*values, name=name, create_type=False), "postgresql"
    )


def _array(item):
    return sa.ARRAY(item).with_variant(sa.JSON(), "sqlite")


def _ts(name: str, nullable: bool = True, **kw) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable, **kw)


def _now_default() -> dict:
    return {"server_default": sa.func.now()}


# ── Upgrade ──────────────────────────────────────────────────────────


def upgrade() -> None:
    ctx = op.get_context()
    is_pg = ctx.dialect.name == "postgresql"
    online = not ctx.as_sql
    bind = op.get_bind() if online else None

    # 1. New enum types (Postgres) + new tables ─────────────────────────
    if is_pg:
        for name in ("business_status", "user_role", "account_status", "email_code_purpose"):
            values = ", ".join(f"'{v}'" for v in ENUMS[name])
            op.execute(f"CREATE TYPE {name} AS ENUM ({values})")

    businesses = op.create_table(
        "businesses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("legal_name", sa.String(200), nullable=True),
        sa.Column("legal_name_normalized", sa.String(200), nullable=True),
        sa.Column("entity_type", sa.String(30), nullable=True),
        sa.Column("industry", sa.String(120), nullable=True),
        sa.Column("operating_countries", _array(sa.CHAR(2)), nullable=True),
        sa.Column("website_url", sa.String(300), nullable=True),
        sa.Column("website_normalized", sa.String(300), nullable=True),
        sa.Column("address_line", sa.String(200), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("pincode", sa.String(10), nullable=True),
        sa.Column("country", sa.CHAR(2), nullable=False, server_default="IN"),
        sa.Column("google_business_url", sa.String(300), nullable=True),
        sa.Column("facebook_url", sa.String(300), nullable=True),
        sa.Column("trade_position", sa.String(10), nullable=True),
        sa.Column("seller_type", sa.String(60), nullable=True),
        sa.Column("export_status", sa.String(40), nullable=True),
        sa.Column("target_markets", _array(sa.CHAR(2)), nullable=True),
        sa.Column("target_buyer_types", _array(sa.String(40)), nullable=True),
        sa.Column("company_introduction", sa.Text(), nullable=True),
        sa.Column("verification_status", _enum("business_status"), nullable=False, server_default="draft"),
        _ts("verification_submitted_at"),
        _ts("verified_at"),
        sa.Column("verification_rejected_reason", sa.String(500), nullable=True),
        _ts("created_at", nullable=False, **_now_default()),
        _ts("updated_at", nullable=False, **_now_default()),
        _ts("deleted_at"),
        sa.CheckConstraint(
            "trade_position IS NULL OR trade_position IN ('seller', 'buyer', 'both')",
            name="ck_businesses_trade_position",
        ),
        sa.CheckConstraint(
            "entity_type IS NULL OR entity_type IN "
            "('proprietorship', 'partnership', 'llp', 'private_ltd', 'public_ltd')",
            name="ck_businesses_entity_type",
        ),
        sa.CheckConstraint("length(country) = 2", name="ck_businesses_country"),
        sa.CheckConstraint(
            "verification_status <> 'verified' OR verified_at IS NOT NULL", name="ck_businesses_verified_has_date"
        ),
        sa.CheckConstraint(
            "verification_status <> 'rejected' OR verification_rejected_reason IS NOT NULL",
            name="ck_businesses_rejected_has_reason",
        ),
        sa.CheckConstraint(
            "verification_status = 'draft' OR verification_submitted_at IS NOT NULL",
            name="ck_businesses_submitted_has_date",
        ),
    )
    op.create_index(
        "uq_businesses_legal_name_normalized", "businesses", ["legal_name_normalized"], unique=True, **_LIVE
    )
    op.create_index("uq_businesses_website_normalized", "businesses", ["website_normalized"], unique=True, **_LIVE)
    op.create_index(
        "ix_businesses_verification_queue", "businesses", ["verification_status", "verification_submitted_at"]
    )

    op.create_table(
        "email_codes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("purpose", _enum("email_code_purpose"), nullable=False),
        sa.Column("code_hash", sa.CHAR(64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        _ts("expires_at", nullable=False),
        _ts("verified_at"),
        _ts("consumed_at"),
        _ts("created_at", nullable=False, **_now_default()),
        sa.CheckConstraint("attempts BETWEEN 0 AND 5", name="ck_email_codes_attempts"),
        sa.CheckConstraint("consumed_at IS NULL OR verified_at IS NOT NULL", name="ck_email_codes_order"),
    )
    op.create_index("ix_email_codes_lookup", "email_codes", ["email", "purpose", sa.text("created_at DESC")])
    op.create_index("ix_email_codes_expires_at", "email_codes", ["expires_at"])

    # 2. Delete accounts that never set a real password ─────────────────
    if online:
        _purge_passwordless(bind)

    # 3. Snapshot rows of tables that are rebuilt ──────────────────────
    reveals = _snapshot_reveals(bind) if online else []
    docs = _snapshot_docs(bind) if online else []
    op.drop_table("contact_reveals")

    # 4. New columns (nullable / defaulted until backfilled) ───────────
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("business_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("role", _enum("user_role"), nullable=False, server_default="owner"))
        batch.add_column(sa.Column("account_status", _enum("account_status"), nullable=False, server_default="active"))
        batch.add_column(sa.Column("full_name", sa.String(100), nullable=True))
        batch.add_column(sa.Column("position", sa.String(120), nullable=True))
        batch.add_column(sa.Column("phone", sa.String(20), nullable=True))
        batch.add_column(sa.Column("phone_normalized", sa.String(20), nullable=True))
        batch.add_column(_ts("consent_at"))
        batch.add_column(sa.Column("consent_version", sa.String(30), nullable=True))
        batch.add_column(_ts("last_login_at"))
    with op.batch_alter_table("products") as batch:
        batch.add_column(sa.Column("business_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("created_by_user_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("currency", sa.CHAR(3), nullable=False, server_default="INR"))
        batch.add_column(_ts("deleted_at"))

    # 5. businesses + users + products backfill ─────────────────────────
    biz_of_user: dict = {}
    if online:
        biz_of_user = _backfill_businesses_and_users(bind, businesses)
        _backfill_products(bind, biz_of_user)

    # 6. verification_docs → business_documents ────────────────────────
    documents = op.create_table(
        "business_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "business_id",
            sa.Uuid(),
            sa.ForeignKey("businesses.id", ondelete="CASCADE", name="fk_business_documents_business_id"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_business_documents_uploaded_by_user_id"),
            nullable=True,
        ),
        sa.Column("doc_type", sa.String(150), nullable=False),
        sa.Column("original_filename", sa.String(300), nullable=False),
        sa.Column("storage_key", sa.String(400), nullable=False),
        sa.Column("mime_type", sa.String(120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", _enum("doc_status"), nullable=False, server_default="pending"),
        sa.Column("rejection_reason", sa.String(500), nullable=True),
        _ts("reviewed_at"),
        sa.Column("reviewed_by", sa.String(200), nullable=True),
        _ts("uploaded_at", nullable=False, **_now_default()),
        sa.CheckConstraint("size_bytes > 0 AND size_bytes <= 10485760", name="ck_business_documents_size"),
        sa.CheckConstraint(
            "status <> 'rejected' OR rejection_reason IS NOT NULL", name="ck_business_documents_rejected_reason"
        ),
    )
    op.create_index(
        "ix_business_documents_business", "business_documents", ["business_id", sa.text("uploaded_at DESC")]
    )
    op.create_index(
        "ix_business_documents_pending",
        "business_documents",
        ["uploaded_at"],
        sqlite_where=sa.text("status = 'pending'"),
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index("ix_business_documents_uploaded_by", "business_documents", ["uploaded_by_user_id"])
    doc_rows = []
    for d in docs:
        business_id = biz_of_user.get(d["user_id"])
        if business_id is None:
            continue
        if not d["size_bytes"] or d["size_bytes"] <= 0 or d["size_bytes"] > 10485760:
            log.warning("0019: dropped document %s with invalid size %r", d["id"], d["size_bytes"])
            continue
        if d["status"] == "rejected" and not d["rejection_reason"]:
            d["rejection_reason"] = PLACEHOLDER_REASON
            log.warning("0019: rejected document %s had no reason — placeholder set", d["id"])
        doc_rows.append(
            {
                "id": d["id"],
                "business_id": business_id,
                "uploaded_by_user_id": d["user_id"],
                "doc_type": d["cert_type"],
                "original_filename": d["filename"],
                "storage_key": f"verification/{d['stored_path']}",
                "mime_type": d["mime_type"],
                "size_bytes": d["size_bytes"],
                "status": d["status"],
                "rejection_reason": d["rejection_reason"],
                "reviewed_at": d["reviewed_at"],
                "reviewed_by": None,
                "uploaded_at": d["uploaded_at"],
            }
        )
    if doc_rows:
        op.bulk_insert(documents, doc_rows)

    # 7. Drop the merged / replaced tables ─────────────────────────────
    op.drop_table("verification_docs")
    op.drop_table("temp_credentials")
    op.drop_table("profiles")
    op.drop_table("business_profiles")

    # 8. users: final shape ────────────────────────────────────────────
    op.execute("DROP INDEX IF EXISTS ix_users_email")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("status")
        batch.drop_column("business_name")
        batch.drop_column("must_change_password")
        batch.drop_column("verification_submitted_at")
        batch.drop_column("verified_at")
        batch.drop_column("verification_rejected_reason")
        batch.alter_column("business_id", existing_type=sa.Uuid(), nullable=False)
        batch.alter_column("full_name", existing_type=sa.String(100), nullable=False)
        batch.alter_column("password_hash", existing_type=sa.String(255), nullable=False)
        batch.alter_column("email_verified_at", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch.create_foreign_key("fk_users_business_id", "businesses", ["business_id"], ["id"], ondelete="RESTRICT")
        batch.create_check_constraint("ck_users_email_lowercase", "email = lower(email)")
        batch.create_check_constraint("ck_users_session_version", "session_version >= 0")
    op.create_index("uq_users_email", "users", ["email"], unique=True)
    op.create_index("uq_users_phone_normalized", "users", ["phone_normalized"], unique=True, **_LIVE)
    op.create_index(
        "uq_users_one_owner_per_business",
        "users",
        ["business_id"],
        unique=True,
        sqlite_where=sa.text("role = 'owner' AND deleted_at IS NULL"),
        postgresql_where=sa.text("role = 'owner' AND deleted_at IS NULL"),
    )
    op.create_index("ix_users_business_id", "users", ["business_id"])
    if is_pg:
        op.execute("DROP TYPE IF EXISTS user_status")

    # 9. products: final shape ─────────────────────────────────────────
    op.execute("DROP INDEX IF EXISTS ix_products_user_id")
    with op.batch_alter_table("products") as batch:
        batch.drop_column("user_id")
        batch.alter_column("business_id", existing_type=sa.Uuid(), nullable=False)
        batch.create_foreign_key("fk_products_business_id", "businesses", ["business_id"], ["id"], ondelete="CASCADE")
        batch.create_foreign_key(
            "fk_products_created_by_user_id", "users", ["created_by_user_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_check_constraint(
            "ck_products_category",
            "category IN ('Rice', 'Sugar', 'Wheat', 'Pulses', 'Spices', 'Oilseeds', "
            "'Cotton', 'Millets', 'Tea', 'Coffee', 'Other')",
        )
        batch.create_check_constraint("ck_products_unit", "unit IN ('MT', 'kg', 'quintal')")
        batch.create_check_constraint("ck_products_currency", "length(currency) = 3")
        batch.create_check_constraint(
            "ck_products_amounts",
            "(quantity IS NULL OR quantity >= 0) AND (moq IS NULL OR moq >= 0) "
            "AND (price_per_unit IS NULL OR price_per_unit >= 0)",
        )
        batch.create_check_constraint("ck_products_moq_le_quantity", "moq IS NULL OR quantity IS NULL OR moq <= quantity")
        batch.create_check_constraint("ck_products_name_length", "length(trim(name)) >= 2")
    op.create_index("ix_products_market", "products", ["category", sa.text("created_at DESC")], **_LIVE)
    op.create_index("ix_products_market_all", "products", [sa.text("created_at DESC")], **_LIVE)
    op.create_index("ix_products_business", "products", ["business_id", sa.text("created_at DESC")], **_LIVE)
    op.create_index("ix_products_created_by", "products", ["created_by_user_id"])

    # 10. contact_reveals: business-level ──────────────────────────────
    contact_reveals = op.create_table(
        "contact_reveals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "buyer_business_id",
            sa.Uuid(),
            sa.ForeignKey("businesses.id", ondelete="CASCADE", name="fk_contact_reveals_buyer_business_id"),
            nullable=False,
        ),
        sa.Column(
            "revealed_by_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_contact_reveals_revealed_by_user_id"),
            nullable=True,
        ),
        sa.Column(
            "seller_business_id",
            sa.Uuid(),
            sa.ForeignKey("businesses.id", ondelete="CASCADE", name="fk_contact_reveals_seller_business_id"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.Uuid(),
            sa.ForeignKey("products.id", ondelete="CASCADE", name="fk_contact_reveals_product_id"),
            nullable=False,
        ),
        _ts("revealed_at", nullable=False, **_now_default()),
        sa.UniqueConstraint("buyer_business_id", "product_id", name="uq_contact_reveals_buyer_product"),
        sa.CheckConstraint("buyer_business_id <> seller_business_id", name="ck_contact_reveals_not_self"),
    )
    op.create_index("ix_contact_reveals_buyer_time", "contact_reveals", ["buyer_business_id", sa.text("revealed_at DESC")])
    op.create_index(
        "ix_contact_reveals_seller_time", "contact_reveals", ["seller_business_id", sa.text("revealed_at DESC")]
    )
    op.create_index("ix_contact_reveals_product", "contact_reveals", ["product_id"])
    op.create_index("ix_contact_reveals_revealed_by", "contact_reveals", ["revealed_by_user_id"])
    reveal_rows, seen = [], set()
    for r in sorted(reveals, key=lambda x: (x["revealed_at"] is None, x["revealed_at"])):
        buyer_biz, seller_biz = biz_of_user.get(r["buyer_id"]), biz_of_user.get(r["seller_id"])
        if buyer_biz is None or seller_biz is None or buyer_biz == seller_biz:
            continue
        key = (buyer_biz, r["product_id"])
        if key in seen:
            continue
        seen.add(key)
        reveal_rows.append(
            {
                "id": r["id"],
                "buyer_business_id": buyer_biz,
                "revealed_by_user_id": r["buyer_id"],
                "seller_business_id": seller_biz,
                "product_id": r["product_id"],
                "revealed_at": r["revealed_at"],
            }
        )
    if reveal_rows:
        op.bulk_insert(contact_reveals, reveal_rows)

    # 11. admin_actions: indexes per the spec ─────────────────────────
    op.drop_index("ix_admin_actions_target", table_name="admin_actions")
    op.drop_index("ix_admin_actions_created_at", table_name="admin_actions")
    op.create_index("ix_admin_actions_target", "admin_actions", ["target_type", "target_id", sa.text("created_at DESC")])
    op.create_index("ix_admin_actions_created_at", "admin_actions", [sa.text("created_at DESC")])
    op.create_index("ix_admin_actions_admin", "admin_actions", ["admin_email", sa.text("created_at DESC")])


def downgrade() -> None:
    raise NotImplementedError("0019_business_entity is one-way — restore a database backup instead.")


# ── Data helpers (online only) ───────────────────────────────────────

_meta = sa.MetaData()
_users = sa.Table(
    "users",
    _meta,
    sa.Column("id", sa.Uuid()),
    sa.Column("email", sa.String(200)),
    sa.Column("password_hash", sa.String(255)),
    sa.Column("status", sa.String(40)),
    sa.Column("email_verified_at", sa.DateTime(timezone=True)),
    sa.Column("verification_submitted_at", sa.DateTime(timezone=True)),
    sa.Column("verified_at", sa.DateTime(timezone=True)),
    sa.Column("verification_rejected_reason", sa.String(500)),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
    sa.Column("deleted_at", sa.DateTime(timezone=True)),
    # added in step 4
    sa.Column("business_id", sa.Uuid()),
    sa.Column("full_name", sa.String(100)),
    sa.Column("position", sa.String(120)),
    sa.Column("phone", sa.String(20)),
    sa.Column("phone_normalized", sa.String(20)),
    sa.Column("consent_at", sa.DateTime(timezone=True)),
    sa.Column("consent_version", sa.String(30)),
)
_profiles = sa.Table(
    "profiles",
    _meta,
    sa.Column("user_id", sa.Uuid()),
    sa.Column("full_name", sa.String(100)),
    sa.Column("phone", sa.String(20)),
    sa.Column("phone_normalized", sa.String(20)),
    sa.Column("position", sa.String(120)),
    sa.Column("address_line", sa.String(200)),
    sa.Column("city", sa.String(100)),
    sa.Column("state", sa.String(100)),
    sa.Column("pincode", sa.String(10)),
    sa.Column("country", sa.String(100)),
    sa.Column("website_url", sa.String(300)),
    sa.Column("google_business_url", sa.String(300)),
    sa.Column("facebook_url", sa.String(300)),
    sa.Column("consent_at", sa.DateTime(timezone=True)),
    sa.Column("consent_version", sa.String(30)),
)
_old_array = sa.ARRAY(sa.String()).with_variant(sa.JSON(), "sqlite")
_bprofiles = sa.Table(
    "business_profiles",
    _meta,
    sa.Column("id", sa.Uuid()),
    sa.Column("user_id", sa.Uuid()),
    sa.Column("legal_name", sa.String(200)),
    sa.Column("legal_name_normalized", sa.String(200)),
    sa.Column("industry", sa.String(120)),
    sa.Column("operating_countries", _old_array),
    sa.Column("website_url", sa.String(300)),
    sa.Column("website_normalized", sa.String(300)),
    sa.Column("trade_position", sa.String(40)),
    sa.Column("seller_type", sa.String(60)),
    sa.Column("export_status", sa.String(40)),
    sa.Column("target_markets", _old_array),
    sa.Column("target_buyer_types", _old_array),
    sa.Column("company_introduction", sa.Text()),
    sa.Column("created_at", sa.DateTime(timezone=True)),
    sa.Column("updated_at", sa.DateTime(timezone=True)),
)
_products = sa.Table(
    "products",
    _meta,
    sa.Column("id", sa.Uuid()),
    sa.Column("user_id", sa.Uuid()),
    sa.Column("name", sa.String(200)),
    sa.Column("category", sa.String(50)),
    sa.Column("unit", sa.String(10)),
    sa.Column("quantity", sa.Numeric(12, 2)),
    sa.Column("moq", sa.Numeric(12, 2)),
    sa.Column("price_per_unit", sa.Numeric(12, 2)),
    sa.Column("business_id", sa.Uuid()),
    sa.Column("created_by_user_id", sa.Uuid()),
)
_reveals = sa.Table(
    "contact_reveals",
    _meta,
    sa.Column("id", sa.Uuid()),
    sa.Column("buyer_id", sa.Uuid()),
    sa.Column("seller_id", sa.Uuid()),
    sa.Column("product_id", sa.Uuid()),
    sa.Column("revealed_at", sa.DateTime(timezone=True)),
)
_docs = sa.Table(
    "verification_docs",
    _meta,
    sa.Column("id", sa.Uuid()),
    sa.Column("user_id", sa.Uuid()),
    sa.Column("cert_type", sa.String(150)),
    sa.Column("filename", sa.String(300)),
    sa.Column("stored_path", sa.String(400)),
    sa.Column("mime_type", sa.String(120)),
    sa.Column("size_bytes", sa.Integer()),
    sa.Column("status", sa.String(20)),
    sa.Column("rejection_reason", sa.String(500)),
    sa.Column("reviewed_at", sa.DateTime(timezone=True)),
    sa.Column("uploaded_at", sa.DateTime(timezone=True)),
)
_temp_creds = sa.Table("temp_credentials", _meta, sa.Column("user_id", sa.Uuid()))


def _purge_passwordless(bind) -> None:
    ids = [r[0] for r in bind.execute(sa.select(_users.c.id).where(_users.c.password_hash.is_(None))).all()]
    if not ids:
        return
    product_ids = [r[0] for r in bind.execute(sa.select(_products.c.id).where(_products.c.user_id.in_(ids))).all()]
    bind.execute(
        sa.delete(_reveals).where(
            sa.or_(
                _reveals.c.buyer_id.in_(ids),
                _reveals.c.seller_id.in_(ids),
                _reveals.c.product_id.in_(product_ids or [uuid.UUID(int=0)]),
            )
        )
    )
    bind.execute(sa.delete(_products).where(_products.c.user_id.in_(ids)))
    bind.execute(sa.delete(_docs).where(_docs.c.user_id.in_(ids)))
    bind.execute(sa.delete(_temp_creds).where(_temp_creds.c.user_id.in_(ids)))
    bind.execute(sa.delete(_profiles).where(_profiles.c.user_id.in_(ids)))
    bind.execute(sa.delete(_bprofiles).where(_bprofiles.c.user_id.in_(ids)))
    bind.execute(sa.delete(_users).where(_users.c.id.in_(ids)))
    log.warning("0019: deleted %d account(s) that never set a password (and their data)", len(ids))


def _snapshot_reveals(bind) -> list[dict]:
    return [dict(r._mapping) for r in bind.execute(sa.select(_reveals)).all()]


def _snapshot_docs(bind) -> list[dict]:
    return [dict(r._mapping) for r in bind.execute(sa.select(_docs)).all()]


def _clip(value, length):
    if value is None:
        return None
    value = str(value).strip()
    return value[:length] or None


def _backfill_businesses_and_users(bind, businesses: sa.Table) -> dict:
    """One business per remaining user (their business profile, or a new
    draft one); the user becomes its owner. Returns {user_id: business_id}."""
    users = bind.execute(
        sa.select(
            _users.c.id,
            _users.c.email,
            _users.c.status,
            _users.c.email_verified_at,
            _users.c.verification_submitted_at,
            _users.c.verified_at,
            _users.c.verification_rejected_reason,
            _users.c.created_at,
            _users.c.updated_at,
            _users.c.deleted_at,
        ).order_by(_users.c.created_at, _users.c.id)
    ).all()
    profiles = {r.user_id: r for r in bind.execute(sa.select(_profiles)).all()}
    bprofiles = {r.user_id: r for r in bind.execute(sa.select(_bprofiles)).all()}
    taken_websites = {r.website_normalized for r in bprofiles.values() if r.website_normalized}

    now = datetime.now(tz=timezone.utc)
    fixes = {"submitted_at": 0, "verified_at": 0, "rejected_reason": 0, "email_lowercased": 0}
    biz_of_user: dict = {}
    rows: list[dict] = []
    for u in users:
        bp = bprofiles.get(u.id)
        p = profiles.get(u.id)
        business_id = bp.id if bp is not None else uuid.uuid4()
        biz_of_user[u.id] = business_id

        website_url = bp.website_url if bp is not None else None
        website_norm = bp.website_normalized if bp is not None else None
        if not website_url and p is not None and p.website_url:
            key = _norm_website(p.website_url)
            if key and key not in taken_websites:
                website_url, website_norm = p.website_url, key
                taken_websites.add(key)
            elif key:
                log.warning("0019: profile website of user %s already used by another business — not copied", u.id)

        country = _alpha2(p.country) if p is not None else None
        if p is not None and p.country and country is None:
            log.warning("0019: unknown country %r for user %s — defaulting to IN", p.country, u.id)
        trade_position = bp.trade_position if bp is not None else None
        if trade_position not in TRADE_POSITIONS:
            if trade_position:
                log.warning("0019: invalid trade_position %r for user %s — cleared", trade_position, u.id)
            trade_position = None

        status = STATUS_MAP.get(str(u.status), "draft")
        fallback_ts = u.updated_at or u.created_at or now
        submitted_at, verified_at, reason = u.verification_submitted_at, u.verified_at, u.verification_rejected_reason
        if status != "draft" and submitted_at is None:
            submitted_at = fallback_ts
            fixes["submitted_at"] += 1
        if status == "verified" and verified_at is None:
            verified_at = fallback_ts
            fixes["verified_at"] += 1
        if status == "rejected" and not reason:
            reason = PLACEHOLDER_REASON
            fixes["rejected_reason"] += 1

        rows.append(
            {
                "id": business_id,
                "legal_name": bp.legal_name if bp is not None else None,
                "legal_name_normalized": bp.legal_name_normalized if bp is not None else None,
                "entity_type": None,
                "industry": bp.industry if bp is not None else None,
                "operating_countries": _alpha2_list(bp.operating_countries) if bp is not None else None,
                "website_url": website_url,
                "website_normalized": website_norm,
                "address_line": p.address_line if p is not None else None,
                "city": p.city if p is not None else None,
                "state": p.state if p is not None else None,
                "pincode": _clip(p.pincode, 10) if p is not None else None,
                "country": country or "IN",
                "google_business_url": p.google_business_url if p is not None else None,
                "facebook_url": p.facebook_url if p is not None else None,
                "trade_position": trade_position,
                "seller_type": bp.seller_type if bp is not None else None,
                "export_status": bp.export_status if bp is not None else None,
                "target_markets": _alpha2_list(bp.target_markets) if bp is not None else None,
                "target_buyer_types": list(bp.target_buyer_types) if bp is not None and bp.target_buyer_types else None,
                "company_introduction": bp.company_introduction if bp is not None else None,
                "verification_status": status,
                "verification_submitted_at": submitted_at,
                "verified_at": verified_at,
                "verification_rejected_reason": reason,
                "created_at": (bp.created_at if bp is not None else None) or u.created_at or now,
                "updated_at": (bp.updated_at if bp is not None else None) or u.updated_at or now,
                "deleted_at": u.deleted_at,
            }
        )
    if rows:
        op.bulk_insert(businesses, rows)

    seen_emails: set[str] = set()
    for u in users:
        email = u.email.strip().lower()
        if email in seen_emails:
            raise RuntimeError(f"0019: two accounts share the email {email!r} (case-insensitively) — merge them first")
        seen_emails.add(email)
        if email != u.email:
            fixes["email_lowercased"] += 1
        p = profiles.get(u.id)
        full_name = _clip(p.full_name, 100) if p is not None else None
        if not full_name:
            full_name = _clip(u.email.split("@", 1)[0], 100) or "Cor1x user"
        phone = p.phone if p is not None else None
        bind.execute(
            sa.update(_users)
            .where(_users.c.id == u.id)
            .values(
                business_id=biz_of_user[u.id],
                email=email,
                full_name=full_name,
                position=p.position if p is not None else None,
                phone=phone,
                phone_normalized=(p.phone_normalized if p is not None else None),
                consent_at=p.consent_at if p is not None else None,
                consent_version=p.consent_version if p is not None else None,
                email_verified_at=u.email_verified_at or u.created_at or now,
            )
        )
    log.info("0019: %d business(es) created for %d user(s)", len(rows), len(users))
    for what, n in fixes.items():
        if n:
            log.warning("0019: fixed %d row(s): %s", n, what)
    return biz_of_user


def _backfill_products(bind, biz_of_user: dict) -> None:
    rows = bind.execute(
        sa.select(
            _products.c.id,
            _products.c.user_id,
            _products.c.name,
            _products.c.category,
            _products.c.unit,
            _products.c.quantity,
            _products.c.moq,
            _products.c.price_per_unit,
        )
    ).all()
    orphans = []
    fixes = {"category": 0, "unit": 0, "amounts": 0, "moq_gt_quantity": 0, "name": 0}
    for r in rows:
        business_id = biz_of_user.get(r.user_id)
        if business_id is None:
            orphans.append(r.id)
            continue
        values = {"business_id": business_id, "created_by_user_id": r.user_id}
        if r.category not in CATEGORIES:
            values["category"] = "Other"
            fixes["category"] += 1
        if r.unit not in UNITS:
            values["unit"] = "MT"
            fixes["unit"] += 1
        quantity, moq = r.quantity, r.moq
        for col in ("quantity", "moq", "price_per_unit"):
            v = getattr(r, col)
            if v is not None and v < 0:
                values[col] = None
                fixes["amounts"] += 1
                if col == "quantity":
                    quantity = None
                if col == "moq":
                    moq = None
        if moq is not None and quantity is not None and moq > quantity:
            values["moq"] = None
            fixes["moq_gt_quantity"] += 1
        if len((r.name or "").strip()) < 2:
            values["name"] = "Untitled listing"
            fixes["name"] += 1
        bind.execute(sa.update(_products).where(_products.c.id == r.id).values(**values))
    for what, n in fixes.items():
        if n:
            log.warning("0019: fixed %d product row(s): %s", n, what)
    if orphans:
        bind.execute(sa.delete(_products).where(_products.c.id.in_(orphans)))
        log.warning("0019: deleted %d product(s) without an owner", len(orphans))
