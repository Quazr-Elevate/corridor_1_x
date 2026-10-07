"""relax users.business_name to nullable — captured at onboarding now

Revision ID: 0012_signup_personal_first
Revises: 0011_onboarding_fields
Create Date: 2026-10-01

Signup now captures personal identity + credentials (email, password,
first name, last name, country of residence). Business name moves into
onboarding step 1 (Company info), so the column has to be nullable.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0012_signup_personal_first"
down_revision: Union[str, None] = "0011_onboarding_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("users", "business_name", nullable=True)


def downgrade() -> None:
    # No safe downgrade — pre-0012 rows can't guarantee a value.
    raise NotImplementedError("0012 is one-way.")
