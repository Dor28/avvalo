"""add opt-in story submissions

Revision ID: 0003_story_submission
Revises: 0002_feedback_nullable
Create Date: 2026-07-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_story_submission"
down_revision: str | None = "0002_feedback_nullable"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "story_submission",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_key", sa.Text(), nullable=False),
        sa.Column("face", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("minimized_text", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_ts", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_story_submission_user_key", "story_submission", ["user_key"])


def downgrade() -> None:
    op.drop_index("ix_story_submission_user_key", table_name="story_submission")
    op.drop_table("story_submission")
