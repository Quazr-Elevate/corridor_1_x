"""Two-factor columns on users and admin_users (no behaviour change)

Revision ID: 0025_totp_columns
Revises: 0024_identity_access
Create Date: 2026-11-15

Build plan 1.2 / CX-070: add the columns while the tables are small, so
turning on 2FA in Phase B is a screen and not a migration on a full table.

* ``totp_secret_encrypted`` + ``totp_secret_key_version`` — AES-256-GCM
  ciphertext and the key version it was written under (``core/crypto.py``).
  A check constraint keeps the pair together.
* ``backup_codes`` — JSON list of hashed one-time codes.

All nullable; nothing reads or writes them yet, so there is no backfill.
Portable (Postgres + SQLite batch ops). Reversible.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025_totp_columns"
down_revision: Union[str, None] = "0024_identity_access"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("users", "admin_users")
PAIR = "(totp_secret_encrypted IS NULL) = (totp_secret_key_version IS NULL)"


def upgrade() -> None:
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("totp_secret_encrypted", sa.Text(), nullable=True))
            batch.add_column(sa.Column("totp_secret_key_version", sa.SmallInteger(), nullable=True))
            batch.add_column(sa.Column("backup_codes", sa.JSON(), nullable=True))
            batch.create_check_constraint(f"ck_{table}_totp_secret_pair", PAIR)


def downgrade() -> None:
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(f"ck_{table}_totp_secret_pair", type_="check")
            batch.drop_column("backup_codes")
            batch.drop_column("totp_secret_key_version")
            batch.drop_column("totp_secret_encrypted")
