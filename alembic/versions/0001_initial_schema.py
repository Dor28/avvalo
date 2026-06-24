"""initial privacy-safe schema (§5.2)

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-24

No table carries submitted content; columns are pseudonymous keys, categorical
fields, rule-id arrays, and metrics only.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "consent",
        sa.Column("user_key", sa.Text(), nullable=False),
        sa.Column("face", sa.Text(), nullable=False),
        sa.Column("notice_version", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_key", "face"),
    )
    op.create_table(
        "check_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_key", sa.Text(), nullable=False),
        sa.Column("face", sa.Text(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_type", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("rule_ids", sa.ARRAY(sa.Text()), nullable=False),
        sa.Column("no_signal", sa.Boolean(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error_class", sa.Text(), nullable=True),
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("ocr_ms", sa.Integer(), nullable=True),
        sa.Column("llm_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("safety_blocked", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_check_event_user_key", "check_event", ["user_key"])
    op.create_index("ix_check_event_ts", "check_event", ["ts"])
    op.create_table(
        "feedback",
        sa.Column("check_id", sa.Uuid(), nullable=False),
        sa.Column("usefulness", sa.Text(), nullable=False),
        sa.Column("next_action", sa.Text(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("check_id"),
    )
    op.create_table(
        "rate_limit",
        sa.Column("user_key", sa.Text(), nullable=False),
        sa.Column("face", sa.Text(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("user_key", "face", "day"),
    )
    op.create_table(
        "deletion_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_key", sa.Text(), nullable=False),
        sa.Column("requested_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_ts", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("deletion_log")
    op.drop_table("rate_limit")
    op.drop_table("feedback")
    op.drop_index("ix_check_event_ts", table_name="check_event")
    op.drop_index("ix_check_event_user_key", table_name="check_event")
    op.drop_table("check_event")
    op.drop_table("consent")
