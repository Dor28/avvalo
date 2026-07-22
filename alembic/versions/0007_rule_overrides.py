"""Add operator-authored rule overrides.

Detection patterns move out of the public repository so new keyword work is not
published; the shipped YAML pack stays as the fallback baseline.

Revision ID: 0007_rule_overrides
Revises: 0006_editorial_posts
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_rule_overrides"
down_revision: str | None = "0006_editorial_posts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rule_override",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("face", sa.Text(), nullable=False),
        sa.Column("rule_id", sa.Text(), nullable=False),
        sa.Column("family", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("message_key", sa.Text(), nullable=False),
        sa.Column("severity", sa.Integer(), nullable=False),
        sa.Column("emits_signal", sa.Text(), nullable=True),
        sa.Column("patterns", sa.JSON(), nullable=False),
        sa.Column("disabled", sa.Boolean(), nullable=False),
        sa.Column("created_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_ts", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("face", "rule_id", name="uq_rule_override_face_rule"),
    )
    op.create_index("ix_rule_override_face", "rule_override", ["face"])
    op.create_index("ix_rule_override_rule_id", "rule_override", ["rule_id"])


def downgrade() -> None:
    op.drop_index("ix_rule_override_rule_id", table_name="rule_override")
    op.drop_index("ix_rule_override_face", table_name="rule_override")
    op.drop_table("rule_override")
