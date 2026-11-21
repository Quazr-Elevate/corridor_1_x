"""Country document rules, quota and group documents, category requirements

Revision ID: 0033_country_rules
Revises: 0032_trader_sessions
Create Date: 2026-11-21

CX-158, CX-164 and CX-174, from the M0–M3 walkthrough review.

* ``country_document_rules`` (A-047): characters x–y of one KYB document's
  number must equal another's. Seeded for India: GSTIN 3–12 = PAN.
* ``countries`` gains ``quota_document_type_id`` (the document that keys the
  free-RFQ quota; India: GSTIN) and ``group_document_type_id`` (a document
  several businesses may share and that the reviewer sees as "related";
  India: PAN) (A-052). India's PAN stops being unique: one PAN stands behind
  a company's GSTIN in each state, and each GSTIN is its own business.
* ``category_certificate_requirements`` (A-049): the documents a listing in
  a category must carry.
* ``spec_parameters``: the approved templates for Sugar, Wheat, Oilseeds,
  Cotton, Millets, Tea, Coffee and Other; Spices moisture and volatile oil
  and Pulses moisture and foreign matter become required. Rows an admin
  already added are kept; a code that exists is not inserted again.

Portable (Postgres + SQLite batch ops). Reversible while no two businesses
share a PAN: downgrade drops the new tables and columns, makes PAN unique
again (failing if a PAN is shared by then) and removes the seeded template
rows that no listing uses.
"""
from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0033_country_rules"
down_revision: Union[str, None] = "0032_trader_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Frozen copies of app/modules/catalog/seed.py at this revision.
# (category, code, name, unit, operator, required, sort, value type)
SPECS = (
    ("Sugar", "icumsa", "ICUMSA colour", "IU", "MAX", True, 10, "number"),
    ("Sugar", "polarisation", "Polarisation", "°Z", "MIN", True, 20, "number"),
    ("Sugar", "moisture", "Moisture", "%", "MAX", True, 30, "number"),
    ("Sugar", "ash", "Ash", "%", "MAX", False, 40, "number"),
    ("Sugar", "solubility", "Solubility", "%", "MIN", False, 50, "number"),
    ("Sugar", "granulation", "Granulation", None, "EQ", False, 60, "text"),
    ("Wheat", "moisture", "Moisture", "%", "MAX", True, 10, "number"),
    ("Wheat", "protein", "Protein", "%", "MIN", True, 20, "number"),
    ("Wheat", "foreign_matter", "Foreign matter", "%", "MAX", True, 30, "number"),
    ("Wheat", "test_weight", "Test weight", "kg/hl", "MIN", False, 40, "number"),
    ("Wheat", "falling_number", "Falling number", "s", "MIN", False, 50, "number"),
    ("Wheat", "damaged_kernels", "Damaged kernels", "%", "MAX", False, 60, "number"),
    ("Oilseeds", "oil_content", "Oil content", "%", "MIN", True, 10, "number"),
    ("Oilseeds", "moisture", "Moisture", "%", "MAX", True, 20, "number"),
    ("Oilseeds", "free_fatty_acid", "Free fatty acid", "%", "MAX", True, 30, "number"),
    ("Oilseeds", "aflatoxin", "Aflatoxin", "ppb", "MAX", True, 40, "number"),
    ("Oilseeds", "foreign_matter", "Foreign matter", "%", "MAX", False, 50, "number"),
    ("Oilseeds", "admixture", "Admixture", "%", "MAX", False, 60, "number"),
    ("Cotton", "staple_length", "Staple length", "mm", "MIN", True, 10, "number"),
    ("Cotton", "micronaire", "Micronaire", None, "EQ", True, 20, "text"),
    ("Cotton", "strength", "Strength", "g/tex", "MIN", True, 30, "number"),
    ("Cotton", "trash", "Trash", "%", "MAX", False, 40, "number"),
    ("Cotton", "moisture", "Moisture", "%", "MAX", False, 50, "number"),
    ("Millets", "moisture", "Moisture", "%", "MAX", True, 10, "number"),
    ("Millets", "foreign_matter", "Foreign matter", "%", "MAX", True, 20, "number"),
    ("Millets", "damaged_grains", "Damaged grains", "%", "MAX", False, 30, "number"),
    ("Millets", "other_grains", "Other grains", "%", "MAX", False, 40, "number"),
    ("Millets", "immature_grains", "Immature or shrivelled grains", "%", "MAX", False, 50, "number"),
    ("Tea", "grade", "Grade", None, "EQ", True, 10, "text"),
    ("Tea", "moisture", "Moisture", "%", "MAX", True, 20, "number"),
    ("Tea", "total_ash", "Total ash", "%", "MAX", False, 30, "number"),
    ("Tea", "water_extract", "Water extract", "%", "MIN", False, 40, "number"),
    ("Tea", "crude_fibre", "Crude fibre", "%", "MAX", False, 50, "number"),
    ("Coffee", "type", "Type", None, "EQ", True, 10, "text"),
    ("Coffee", "moisture", "Moisture", "%", "MAX", True, 20, "number"),
    ("Coffee", "screen_size", "Screen size", "screen", "MIN", True, 30, "number"),
    ("Coffee", "defects", "Defects per 300 g", "count", "MAX", True, 40, "number"),
    ("Coffee", "cup_score", "Cup score", "points", "MIN", False, 50, "number"),
    ("Other", "moisture", "Moisture", "%", "MAX", False, 10, "number"),
    ("Other", "foreign_matter", "Foreign matter", "%", "MAX", False, 20, "number"),
)
NOW_REQUIRED = (("Spices", "moisture"), ("Spices", "volatile_oil"), ("Pulses", "moisture"), ("Pulses", "foreign_matter"))
REQUIREMENTS = (
    ("Rice", "coa"), ("Spices", "coa"), ("Spices", "quality_test_report"), ("Pulses", "coa"), ("Sugar", "coa"),
    ("Wheat", "coa"), ("Oilseeds", "coa"), ("Oilseeds", "quality_test_report"), ("Cotton", "quality_test_report"),
    ("Millets", "coa"), ("Tea", "product_certificate"), ("Coffee", "quality_test_report"),
)


def upgrade() -> None:
    bind = op.get_bind()
    op.create_table(
        "country_document_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("country", sa.CHAR(2), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False, server_default="slice_equals"),
        sa.Column("source_type_id", sa.Uuid(), nullable=False),
        sa.Column("source_start", sa.SmallInteger(), nullable=False),
        sa.Column("source_end", sa.SmallInteger(), nullable=False),
        sa.Column("target_type_id", sa.Uuid(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["country"], ["countries.code"], name="fk_country_document_rules_country", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_type_id"], ["kyb_document_types.id"], name="fk_country_document_rules_source", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_type_id"], ["kyb_document_types.id"], name="fk_country_document_rules_target", ondelete="CASCADE"),
        sa.CheckConstraint("kind IN ('slice_equals')", name="ck_country_document_rules_kind"),
        sa.CheckConstraint("source_start >= 1 AND source_end >= source_start", name="ck_country_document_rules_range"),
        sa.CheckConstraint("source_type_id <> target_type_id", name="ck_country_document_rules_two_documents"),
    )
    op.create_index("ix_country_document_rules_country", "country_document_rules", ["country"])
    with op.batch_alter_table("countries") as batch:
        batch.add_column(sa.Column("quota_document_type_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("group_document_type_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_countries_quota_document_type_id", "kyb_document_types", ["quota_document_type_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_foreign_key(
            "fk_countries_group_document_type_id", "kyb_document_types", ["group_document_type_id"], ["id"], ondelete="SET NULL"
        )
    op.create_table(
        "category_certificate_requirements",
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("certificate_type_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("category", "certificate_type_id"),
        sa.ForeignKeyConstraint(
            ["certificate_type_id"], ["certificate_types.id"], name="fk_category_cert_req_type_id", ondelete="CASCADE"
        ),
    )

    # India: the rule, the two links, and PAN shared between GSTINs.
    types = {
        code: tid
        for tid, code in bind.execute(
            sa.text("SELECT id, code FROM kyb_document_types WHERE country = 'IN' AND code IN ('gstin', 'pan')")
        )
    }
    if {"gstin", "pan"} <= types.keys():
        rules = sa.table(
            "country_document_rules", sa.column("id", sa.Uuid()), sa.column("country", sa.CHAR(2)),
            sa.column("kind", sa.String), sa.column("source_type_id", sa.Uuid()), sa.column("source_start", sa.SmallInteger),
            sa.column("source_end", sa.SmallInteger), sa.column("target_type_id", sa.Uuid()), sa.column("active", sa.Boolean),
        )
        op.bulk_insert(rules, [{
            "id": uuid.uuid4(), "country": "IN", "kind": "slice_equals", "source_type_id": _uuid(types["gstin"]),
            "source_start": 3, "source_end": 12, "target_type_id": _uuid(types["pan"]), "active": True,
        }])
        bind.execute(
            sa.text("UPDATE countries SET quota_document_type_id = :q, group_document_type_id = :g WHERE code = 'IN'"),
            {"q": types["gstin"], "g": types["pan"]},
        )
        bind.execute(sa.text("UPDATE kyb_document_types SET is_unique = :no WHERE id = :pan"), {"no": False, "pan": types["pan"]})
        bind.execute(sa.text("UPDATE business_documents SET value_unique = :no WHERE document_type_id = :pan"),
                     {"no": False, "pan": types["pan"]})

    # Templates.
    existing = {(c, code) for c, code in bind.execute(sa.text("SELECT category, code FROM spec_parameters"))}
    specs = sa.table(
        "spec_parameters", sa.column("id", sa.Uuid()), sa.column("category", sa.String), sa.column("code", sa.String),
        sa.column("name", sa.String), sa.column("value_type", sa.String), sa.column("unit", sa.String),
        sa.column("default_operator", sa.String), sa.column("is_required", sa.Boolean),
        sa.column("sort_order", sa.Integer), sa.column("active", sa.Boolean),
    )
    op.bulk_insert(specs, [
        {"id": uuid.uuid4(), "category": c, "code": code, "name": name, "value_type": kind, "unit": unit,
         "default_operator": op_, "is_required": req, "sort_order": sort, "active": True}
        for c, code, name, unit, op_, req, sort, kind in SPECS if (c, code) not in existing
    ])
    for category, code in NOW_REQUIRED:
        bind.execute(
            sa.text("UPDATE spec_parameters SET is_required = :yes WHERE category = :c AND code = :code"),
            {"yes": True, "c": category, "code": code},
        )
    certs = {code: tid for tid, code in bind.execute(sa.text("SELECT id, code FROM certificate_types WHERE category = '*'"))}
    reqs = sa.table("category_certificate_requirements", sa.column("category", sa.String), sa.column("certificate_type_id", sa.Uuid()))
    op.bulk_insert(reqs, [
        {"category": c, "certificate_type_id": _uuid(certs[code])} for c, code in REQUIREMENTS if code in certs
    ])


def _uuid(value) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_table("category_certificate_requirements")
    for category, code in NOW_REQUIRED:
        bind.execute(
            sa.text("UPDATE spec_parameters SET is_required = :no WHERE category = :c AND code = :code"),
            {"no": False, "c": category, "code": code},
        )
    for c, code, *_ in SPECS:
        bind.execute(
            sa.text(
                "DELETE FROM spec_parameters WHERE category = :c AND code = :code "
                "AND id NOT IN (SELECT parameter_id FROM product_specs)"
            ),
            {"c": c, "code": code},
        )
    pan = bind.execute(sa.text("SELECT id FROM kyb_document_types WHERE country = 'IN' AND code = 'pan'")).scalar()
    if pan is not None:
        bind.execute(sa.text("UPDATE kyb_document_types SET is_unique = :yes WHERE id = :pan"), {"yes": True, "pan": pan})
        bind.execute(sa.text("UPDATE business_documents SET value_unique = :yes WHERE document_type_id = :pan"),
                     {"yes": True, "pan": pan})
    with op.batch_alter_table("countries") as batch:
        batch.drop_constraint("fk_countries_group_document_type_id", type_="foreignkey")
        batch.drop_constraint("fk_countries_quota_document_type_id", type_="foreignkey")
        batch.drop_column("group_document_type_id")
        batch.drop_column("quota_document_type_id")
    op.drop_index("ix_country_document_rules_country", table_name="country_document_rules")
    op.drop_table("country_document_rules")
