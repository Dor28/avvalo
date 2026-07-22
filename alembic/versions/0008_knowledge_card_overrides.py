"""Add operator-authored knowledge card overrides.

Cards move out of the public repository so new card work is not published; the
shipped YAML base stays as the fallback baseline.

Revision ID: 0008_knowledge_card_overrides
Revises: 0007_rule_overrides
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_knowledge_card_overrides"
down_revision: str | None = "0007_rule_overrides"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_card_override",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("face", sa.Text(), nullable=False),
        sa.Column("card_id", sa.Text(), nullable=False),
        sa.Column("card_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reviewer", sa.Text(), nullable=False),
        sa.Column("trigger_rule_ids", sa.JSON(), nullable=False),
        sa.Column("trigger_signal_kinds", sa.JSON(), nullable=False),
        sa.Column("retrieval_aliases", sa.JSON(), nullable=False),
        sa.Column("mechanism", sa.Text(), nullable=False),
        sa.Column("red_flags", sa.JSON(), nullable=False),
        sa.Column("verify_steps", sa.JSON(), nullable=False),
        sa.Column("questions", sa.JSON(), nullable=False),
        sa.Column("reviewed_case_ids", sa.JSON(), nullable=False),
        sa.Column("created_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_ts", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("face", "card_id", name="uq_knowledge_card_override_face_card"),
    )
    op.create_index("ix_knowledge_card_override_face", "knowledge_card_override", ["face"])
    op.create_index("ix_knowledge_card_override_card_id", "knowledge_card_override", ["card_id"])
    op.create_index("ix_knowledge_card_override_status", "knowledge_card_override", ["status"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_card_override_status", table_name="knowledge_card_override")
    op.drop_index("ix_knowledge_card_override_card_id", table_name="knowledge_card_override")
    op.drop_index("ix_knowledge_card_override_face", table_name="knowledge_card_override")
    op.drop_table("knowledge_card_override")
