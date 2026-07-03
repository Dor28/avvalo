"""allow usefulness feedback before next action

Revision ID: 0002_feedback_nullable
Revises: 0001_initial
Create Date: 2026-06-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_feedback_nullable"
down_revision: str | None = "0001_initial"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("feedback", "next_action", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE feedback SET next_action = 'not_sure' WHERE next_action IS NULL")
    op.alter_column("feedback", "next_action", existing_type=sa.Text(), nullable=False)
