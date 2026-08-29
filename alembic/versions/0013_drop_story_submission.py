"""Drop the legacy story_submission table.

Revision ID: 0013_drop_story_submission
Revises: 0012_rule_precision_fields

The retired story-capture flow left one table behind. It has had no writer and
no product reader since the flow was removed; only retention and
``/delete_my_data`` still swept it. ``story_submission.minimized_text`` was the
only text column in the schema, so dropping the table leaves no column anywhere
that can hold submitted content.

The founder authorized this purge, which V1_TECHNICAL_PLAN §7 required before
the table could go. ``downgrade`` recreates the structure, not the rows: the
data is deleted deliberately and is not recoverable from a downgrade.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013_drop_story_submission"
down_revision: str | None = "0012_rule_precision_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_story_submission_user_key", table_name="story_submission")
    op.drop_table("story_submission")


def downgrade() -> None:
    op.create_table(
        "story_submission",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_key", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("minimized_text", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_ts", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_story_submission_user_key", "story_submission", ["user_key"])
