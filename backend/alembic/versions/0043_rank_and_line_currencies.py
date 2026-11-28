"""Ranked matches and cost lines in their own currency

Revision ID: 0043_rank_and_line_currencies
Revises: 0042_deal_documents
Create Date: 2026-11-28

CX-177, CX-185 (A-082); docs/04_data_model.md → "Ranking and cost-line currencies (0043)".

* ``rfq_matches.score`` (0–100, check) and ``score_parts``: null for rows
  made before this revision and for desk-added matches.
* ``cost_sheets.line_entries``: cost lines entered in another currency, with
  the rate they were converted at. Existing sheets get ``{}``: every line was
  in the purchase currency, which is what ``{}`` means.

Reversible: downgrade drops the three columns.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0043_rank_and_line_currencies"
down_revision: Union[str, None] = "0042_deal_documents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("rfq_matches") as batch:
        batch.add_column(sa.Column("score", sa.SmallInteger(), nullable=True))
        batch.add_column(sa.Column("score_parts", sa.JSON(), nullable=True))
        batch.create_check_constraint("ck_rfq_matches_score", "score IS NULL OR (score >= 0 AND score <= 100)")
    with op.batch_alter_table("cost_sheets") as batch:
        batch.add_column(sa.Column("line_entries", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    with op.batch_alter_table("cost_sheets") as batch:
        batch.drop_column("line_entries")
    with op.batch_alter_table("rfq_matches") as batch:
        batch.drop_constraint("ck_rfq_matches_score", type_="check")
        batch.drop_column("score_parts")
        batch.drop_column("score")
