"""add privacy-safe knowledge retrieval metadata

Revision ID: 0004_knowledge_metadata
Revises: 0003_story_submission
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_knowledge_metadata"
down_revision: str | None = "0003_story_submission"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    empty_text_array = sa.text("'{}'::text[]")
    op.add_column(
        "check_event",
        sa.Column(
            "knowledge_card_ids",
            sa.ARRAY(sa.Text()),
            server_default=empty_text_array,
            nullable=False,
        ),
    )
    op.add_column(
        "check_event",
        sa.Column(
            "reviewed_case_ids",
            sa.ARRAY(sa.Text()),
            server_default=empty_text_array,
            nullable=False,
        ),
    )
    op.add_column("check_event", sa.Column("retrieval_mode", sa.Text(), nullable=True))
    op.add_column("check_event", sa.Column("retrieval_status", sa.Text(), nullable=True))
    op.add_column("check_event", sa.Column("kb_version", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("check_event", "kb_version")
    op.drop_column("check_event", "retrieval_status")
    op.drop_column("check_event", "retrieval_mode")
    op.drop_column("check_event", "reviewed_case_ids")
    op.drop_column("check_event", "knowledge_card_ids")
