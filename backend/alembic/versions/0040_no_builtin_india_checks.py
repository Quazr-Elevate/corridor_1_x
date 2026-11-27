"""No built-in GSTIN / PAN checks

Revision ID: 0040_no_builtin_india_checks
Revises: 0039_samples
Create Date: 2026-11-27

Number checks for one country's documents are not built into Corridor: the
reviewer (and, later, the upstream verification provider) checks them. The
database shipped India with two of its own:

* the GSTIN and PAN format patterns from ``0021_kyb_profile``, and
* the "PAN = characters 3 to 12 of the GSTIN" rule from ``0033_country_rules``.

This clears those patterns and switches the rule off, but only where they
still hold the values the migrations seeded: an admin's own change stays.
Admins can still set a pattern or a rule per country from the console.

Portable. Reversible: downgrade restores the seeded values on the same rows.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0040_no_builtin_india_checks"
down_revision: Union[str, None] = "0039_samples"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PATTERNS = {
    "gstin": r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]",
    "pan": r"[A-Z]{5}[0-9]{4}[A-Z]",
}

_SEEDED_RULE = """
    country = 'IN' AND kind = 'slice_equals' AND source_start = 3 AND source_end = 12
    AND source_type_id = (SELECT id FROM kyb_document_types WHERE country = 'IN' AND code = 'gstin')
    AND target_type_id = (SELECT id FROM kyb_document_types WHERE country = 'IN' AND code = 'pan')
"""


def upgrade() -> None:
    for code, pattern in PATTERNS.items():
        op.execute(
            sa.text(
                "UPDATE kyb_document_types SET value_pattern = NULL "
                "WHERE country = 'IN' AND code = :code AND value_pattern = :pattern"
            ).bindparams(code=code, pattern=pattern)
        )
    op.execute(sa.text(f"UPDATE country_document_rules SET active = :off WHERE {_SEEDED_RULE}").bindparams(off=False))


def downgrade() -> None:
    for code, pattern in PATTERNS.items():
        op.execute(
            sa.text(
                "UPDATE kyb_document_types SET value_pattern = :pattern "
                "WHERE country = 'IN' AND code = :code AND value_pattern IS NULL"
            ).bindparams(code=code, pattern=pattern)
        )
    op.execute(sa.text(f"UPDATE country_document_rules SET active = :on WHERE {_SEEDED_RULE}").bindparams(on=True))
