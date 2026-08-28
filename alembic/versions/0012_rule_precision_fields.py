"""Add the optional rule-precision fields to operator rule overrides.

``exclude_patterns``, ``match_mode``, and ``requires`` (PIPELINE_V2 §6) are all
optional: NULL on every existing row, which the loader reads as no exclusions,
substring matching, and no co-occurrence gate — the behavior those rows have
today.

Revision ID: 0012_rule_precision_fields
Revises: 0011_editorial_post_covers
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012_rule_precision_fields"
down_revision: str | None = "0011_editorial_post_covers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("rule_override", sa.Column("exclude_patterns", sa.JSON(), nullable=True))
    op.add_column("rule_override", sa.Column("match_mode", sa.Text(), nullable=True))
    op.add_column("rule_override", sa.Column("requires", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("rule_override", "requires")
    op.drop_column("rule_override", "match_mode")
    op.drop_column("rule_override", "exclude_patterns")
