"""Add router health metadata and local URL blocklist.

Revision ID: 0005_improvement_backlog
Revises: 0004_knowledge_metadata
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_improvement_backlog"
down_revision: str | None = "0004_knowledge_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("check_event", sa.Column("router_status", sa.Text(), nullable=True))
    op.create_table(
        "url_blocklist",
        sa.Column("domain_hash", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("domain_hash", "source"),
    )


def downgrade() -> None:
    op.drop_table("url_blocklist")
    op.drop_column("check_event", "router_status")
