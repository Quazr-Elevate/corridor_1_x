"""verification_docs: cert_type + per-doc status

Revision ID: 0014_doc_cert_type_status
Revises: 0013_verification_docs
Create Date: 2026-10-05

Adds the fields needed for the new certification-picker flow:

  cert_type    — free-text category ("GST Certificate", "FSSAI License", ...)
  status       — pending | approved | rejected, per-doc admin lifecycle
  reviewed_at  — timestamp of the admin decision

Existing rows (uploads from before this migration) are classified as
"Other" and left pending so admin can re-review them.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0014_doc_cert_type_status"
down_revision: Union[str, None] = "0013_verification_docs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # cert_type — nullable at first so the ALTER succeeds on populated tables,
    # then backfilled, then flipped to NOT NULL.
    op.add_column(
        "verification_docs",
        sa.Column("cert_type", sa.String(length=150), nullable=True),
    )
    op.execute(
        "UPDATE verification_docs SET cert_type = 'Other' WHERE cert_type IS NULL"
    )
    op.alter_column("verification_docs", "cert_type", nullable=False)

    # Postgres needs the enum type to exist before the column references it.
    if dialect == "postgresql":
        op.execute("CREATE TYPE doc_status AS ENUM ('pending', 'approved', 'rejected')")

    op.add_column(
        "verification_docs",
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "rejected", name="doc_status"),
            nullable=True,
            server_default="pending",
        ),
    )
    op.execute("UPDATE verification_docs SET status = 'pending' WHERE status IS NULL")
    op.alter_column("verification_docs", "status", nullable=False)

    op.add_column(
        "verification_docs",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("verification_docs", "reviewed_at")
    op.drop_column("verification_docs", "status")
    op.drop_column("verification_docs", "cert_type")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS doc_status")
