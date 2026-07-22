"""Add founder-authored trilingual editorial posts.

Revision ID: 0006_editorial_posts
Revises: 0005_improvement_backlog
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_editorial_posts"
down_revision: str | None = "0005_improvement_backlog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "editorial_post",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("title_uz_latn", sa.Text(), nullable=False),
        sa.Column("summary_uz_latn", sa.Text(), nullable=False),
        sa.Column("article_uz_latn", sa.Text(), nullable=False),
        sa.Column("title_uz_cyrl", sa.Text(), nullable=False),
        sa.Column("summary_uz_cyrl", sa.Text(), nullable=False),
        sa.Column("article_uz_cyrl", sa.Text(), nullable=False),
        sa.Column("title_ru", sa.Text(), nullable=False),
        sa.Column("summary_ru", sa.Text(), nullable=False),
        sa.Column("article_ru", sa.Text(), nullable=False),
        sa.Column("created_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_ts", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("state IN ('draft', 'published')", name="ck_editorial_post_state"),
        sa.CheckConstraint(
            "category IN ('payments', 'phishing', 'marketplace', 'jobs', 'accounts', 'documents')",
            name="ck_editorial_post_category",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_editorial_post_slug", "editorial_post", ["slug"], unique=True)
    op.create_index("ix_editorial_post_category", "editorial_post", ["category"])
    op.create_index("ix_editorial_post_state", "editorial_post", ["state"])
    op.create_index(
        "ix_editorial_post_publication",
        "editorial_post",
        ["state", "published_ts"],
    )


def downgrade() -> None:
    op.drop_index("ix_editorial_post_publication", table_name="editorial_post")
    op.drop_index("ix_editorial_post_state", table_name="editorial_post")
    op.drop_index("ix_editorial_post_category", table_name="editorial_post")
    op.drop_index("ix_editorial_post_slug", table_name="editorial_post")
    op.drop_table("editorial_post")
