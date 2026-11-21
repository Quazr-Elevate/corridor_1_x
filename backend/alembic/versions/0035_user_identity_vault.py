"""User identity vault: name, email and phone leave users

Revision ID: 0035_user_identity_vault
Revises: 0034_credit_expiry_invoices
Create Date: 2026-11-21

CX-149 (A-028, A-043, A-070); docs/04_data_model.md → "User identity vault (0035)".

* new table ``user_identities``: one row per live trader account with their
  full name, work email (the sign-in handle, unique, lowercase) and phone
  (unique on its normalized form). Only ``app/modules/masking`` reads it.
* ``users`` loses ``email``, ``full_name``, ``phone`` and ``phone_normalized``,
  their two unique indexes and the lowercase check.

Existing rows: every live user gets a vault row with its values copied
across. A soft-deleted user gets none: their email was already replaced by a
placeholder, and deletion now removes the vault row instead.

Portable (Postgres + SQLite batch ops). Reversible: downgrade copies the
values back; users without a vault row get the old deleted-account
placeholders.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0035_user_identity_vault"
down_revision: Union[str, None] = "0034_credit_expiry_invoices"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MOVED = (
    ("full_name", sa.String(100)),
    ("email", sa.String(200)),
    ("phone", sa.String(20)),
    ("phone_normalized", sa.String(20)),
)
_COLUMNS = ", ".join(name for name, _ in MOVED)
_LIVE = {"sqlite_where": sa.text("deleted_at IS NULL"), "postgresql_where": sa.text("deleted_at IS NULL")}


def upgrade() -> None:
    op.create_table(
        "user_identities",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("phone_normalized", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("email = lower(email)", name="ck_user_identities_email_lowercase"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_user_identities_user_id"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.execute(
        f"INSERT INTO user_identities (user_id, {_COLUMNS}) SELECT id, {_COLUMNS} FROM users WHERE deleted_at IS NULL"
    )
    op.create_index("uq_user_identities_email", "user_identities", ["email"], unique=True)
    op.create_index("uq_user_identities_phone_normalized", "user_identities", ["phone_normalized"], unique=True)

    op.drop_index("uq_users_email", table_name="users")
    op.drop_index("uq_users_phone_normalized", table_name="users")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("ck_users_email_lowercase", type_="check")
        for name, _ in MOVED:
            batch.drop_column(name)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        for name, type_ in MOVED:
            batch.add_column(sa.Column(name, type_, nullable=True))
    for name, _ in MOVED:
        op.execute(
            f"UPDATE users SET {name} = (SELECT i.{name} FROM user_identities i WHERE i.user_id = users.id)"
        )
    # Accounts deleted while the vault held their row get the placeholders
    # deletion used to write.
    bind = op.get_bind()
    for (user_id,) in bind.execute(sa.text("SELECT id FROM users WHERE email IS NULL")).fetchall():
        bind.execute(
            sa.text("UPDATE users SET email = :email, full_name = 'Deleted user' WHERE id = :id"),
            {"email": f"deleted-{user_id}@deleted.local".lower(), "id": user_id},
        )
    with op.batch_alter_table("users") as batch:
        batch.alter_column("email", existing_type=sa.String(200), nullable=False)
        batch.alter_column("full_name", existing_type=sa.String(100), nullable=False)
        batch.create_check_constraint("ck_users_email_lowercase", "email = lower(email)")
    op.create_index("uq_users_email", "users", ["email"], unique=True)
    op.create_index("uq_users_phone_normalized", "users", ["phone_normalized"], unique=True, **_LIVE)
    op.drop_table("user_identities")
