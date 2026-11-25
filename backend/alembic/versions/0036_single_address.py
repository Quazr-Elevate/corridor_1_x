"""One address field; countries lose the India-shaped address labels

Revision ID: 0036_single_address
Revises: 0035_user_identity_vault
Create Date: 2026-11-24

A registered address is written as one block of text, the way the company
writes it itself. The split into line / city / postcode only ever fitted
India, and the per-country labels that papered over it (``region_label``,
``postal_label``, ``postal_pattern``) went with it: the UAE has no postal
code to label, and a pattern per country is a rule nobody outside India
asked for.

* ``business_identities.address_line`` becomes the whole address (400
  chars). ``city`` and ``pincode`` are folded into it, comma-separated, and
  dropped. The address stays inside the vault.
* ``businesses.state`` is untouched: it is the region the market shows on a
  listing (CX-068), it never held a street, and it is not in the vault.
* ``countries`` loses ``region_label``, ``postal_label`` and
  ``postal_pattern``.

One-way for the merged values: downgrade restores the columns and the
labels' defaults, but the address stays in one piece — the commas it was
joined on are not a reliable way back.

Portable (Postgres + SQLite batch ops).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0036_single_address"
down_revision: Union[str, None] = "0035_user_identity_vault"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    identities = sa.table(
        "business_identities",
        sa.column("business_id", sa.Uuid()),
        sa.column("address_line", sa.String()),
        sa.column("city", sa.String()),
        sa.column("pincode", sa.String()),
    )
    bind = op.get_bind()

    with op.batch_alter_table("business_identities") as batch:
        batch.alter_column("address_line", type_=sa.String(400), existing_type=sa.String(200), existing_nullable=True)

    # Join what the company already typed, in reading order, skipping blanks.
    for row in bind.execute(sa.select(identities.c.business_id, identities.c.address_line, identities.c.city, identities.c.pincode)):
        parts = [(p or "").strip() for p in (row.address_line, row.city, row.pincode)]
        merged = ", ".join(p for p in parts if p)[:400]
        if merged != (row.address_line or ""):
            bind.execute(
                identities.update().where(identities.c.business_id == row.business_id).values(address_line=merged or None)
            )

    with op.batch_alter_table("business_identities") as batch:
        batch.drop_column("city")
        batch.drop_column("pincode")

    with op.batch_alter_table("countries") as batch:
        batch.drop_column("region_label")
        batch.drop_column("postal_label")
        batch.drop_column("postal_pattern")


def downgrade() -> None:
    with op.batch_alter_table("business_identities") as batch:
        batch.add_column(sa.Column("city", sa.String(100), nullable=True))
        batch.add_column(sa.Column("pincode", sa.String(10), nullable=True))
        batch.alter_column("address_line", type_=sa.String(200), existing_type=sa.String(400), existing_nullable=True)

    with op.batch_alter_table("countries") as batch:
        batch.add_column(
            sa.Column("region_label", sa.String(30), nullable=False, server_default="State / region")
        )
        batch.add_column(sa.Column("postal_label", sa.String(30), nullable=False, server_default="Postal code"))
        batch.add_column(sa.Column("postal_pattern", sa.String(100), nullable=True))
