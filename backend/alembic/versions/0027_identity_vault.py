"""Identity vault and company codes

Revision ID: 0027_identity_vault
Revises: 0026_listing_review
Create Date: 2026-11-16

Build plan 18.1–18.2 (CX-079, CX-080); docs/04_data_model.md → "Identity
vault (0027)".

* new table ``business_identities`` — one row per business with its legal
  name, website, address line, city, PIN code and social links (and the two
  normalized columns behind the UNIQUE indexes). Only ``app/modules/masking``
  reads it.
* ``businesses`` loses those nine columns and their two partial indexes, and
  gains ``company_code`` (``{ISO2}-{6 random digits}``, unique).

Existing rows: every live business gets a vault row with its values copied
across. A soft-deleted business gets none — its name and address were only
kept because nothing removed them, and erasure now deletes the vault row —
so the UNIQUE indexes no longer need ``WHERE deleted_at IS NULL``. Every
verified business gets a company code.

Portable (Postgres + SQLite batch ops). Reversible: downgrade copies the
values back; names of soft-deleted businesses and all company codes are lost.
"""
from __future__ import annotations

import secrets
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027_identity_vault"
down_revision: Union[str, None] = "0026_listing_review"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MOVED = (
    ("legal_name", sa.String(200)),
    ("legal_name_normalized", sa.String(200)),
    ("website_url", sa.String(300)),
    ("website_normalized", sa.String(300)),
    ("address_line", sa.String(200)),
    ("city", sa.String(100)),
    ("pincode", sa.String(10)),
    ("google_business_url", sa.String(300)),
    ("facebook_url", sa.String(300)),
)
_COLUMNS = ", ".join(name for name, _ in MOVED)
_LIVE = {"sqlite_where": sa.text("deleted_at IS NULL"), "postgresql_where": sa.text("deleted_at IS NULL")}


def upgrade() -> None:
    op.create_table(
        "business_identities",
        sa.Column("business_id", sa.Uuid(), nullable=False),
        *(sa.Column(name, type_, nullable=True) for name, type_ in MOVED),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["business_id"], ["businesses.id"], ondelete="CASCADE", name="fk_business_identities_business_id"
        ),
        sa.PrimaryKeyConstraint("business_id"),
    )
    op.execute(
        f"INSERT INTO business_identities (business_id, {_COLUMNS}) "
        f"SELECT id, {_COLUMNS} FROM businesses WHERE deleted_at IS NULL"
    )
    op.create_index(
        "uq_business_identities_legal_name_normalized", "business_identities", ["legal_name_normalized"], unique=True
    )
    op.create_index(
        "uq_business_identities_website_normalized", "business_identities", ["website_normalized"], unique=True
    )

    op.drop_index("uq_businesses_legal_name_normalized", table_name="businesses")
    op.drop_index("uq_businesses_website_normalized", table_name="businesses")
    with op.batch_alter_table("businesses") as batch:
        for name, _ in MOVED:
            batch.drop_column(name)
        batch.add_column(sa.Column("company_code", sa.String(12), nullable=True))

    bind = op.get_bind()
    verified = bind.execute(
        sa.text("SELECT id, country FROM businesses WHERE verification_status = 'verified' AND deleted_at IS NULL")
    ).fetchall()
    issued: set[str] = set()
    for business_id, country in verified:
        code = _new_code(country, issued)
        bind.execute(sa.text("UPDATE businesses SET company_code = :code WHERE id = :id"), {"code": code, "id": business_id})
    op.create_index("uq_businesses_company_code", "businesses", ["company_code"], unique=True)


def _new_code(country: str, issued: set[str]) -> str:
    while True:
        code = f"{(country or 'IN').upper()}-{secrets.randbelow(10**6):06d}"
        if code not in issued:
            issued.add(code)
            return code


def downgrade() -> None:
    op.drop_index("uq_businesses_company_code", table_name="businesses")
    with op.batch_alter_table("businesses") as batch:
        batch.drop_column("company_code")
        for name, type_ in MOVED:
            batch.add_column(sa.Column(name, type_, nullable=True))
    for name, _ in MOVED:
        op.execute(
            f"UPDATE businesses SET {name} = (SELECT i.{name} FROM business_identities i "
            "WHERE i.business_id = businesses.id)"
        )
    op.create_index(
        "uq_businesses_legal_name_normalized", "businesses", ["legal_name_normalized"], unique=True, **_LIVE
    )
    op.create_index("uq_businesses_website_normalized", "businesses", ["website_normalized"], unique=True, **_LIVE)
    op.drop_table("business_identities")
