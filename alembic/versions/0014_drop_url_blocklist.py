"""Drop the url_blocklist table with the URL-reputation feature.

Revision ID: 0014_drop_url_blocklist
Revises: 0013_drop_story_submission

The local URL-reputation lookup was never enabled: ``URL_REPUTATION_ENABLED``
defaulted to false and the shipped domain list was empty, so the table changed
no answer. The founder chose to remove the feature rather than keep carrying it,
so the table goes with the code that filled it.

``downgrade`` recreates the structure. The rows are not restored; they were
hashes derived from public feeds and are rebuilt by re-fetching, not by a
downgrade.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014_drop_url_blocklist"
down_revision: str | None = "0013_drop_story_submission"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("url_blocklist")


def downgrade() -> None:
    op.create_table(
        "url_blocklist",
        sa.Column("domain_hash", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("domain_hash", "source"),
    )
