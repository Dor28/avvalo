"""Add optional founder-authored cover photos to editorial posts.

Revision ID: 0011_editorial_post_covers
Revises: 0010_knowledge_card_overrides
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011_editorial_post_covers"
down_revision: str | None = "0010_knowledge_card_overrides"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("editorial_post", sa.Column("cover_bytes", sa.LargeBinary(), nullable=True))
    op.add_column(
        "editorial_post", sa.Column("cover_media_type", sa.String(length=32), nullable=True)
    )
    op.add_column("editorial_post", sa.Column("cover_alt_uz_latn", sa.Text(), nullable=True))
    op.add_column("editorial_post", sa.Column("cover_alt_ru", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("editorial_post", "cover_alt_ru")
    op.drop_column("editorial_post", "cover_alt_uz_latn")
    op.drop_column("editorial_post", "cover_media_type")
    op.drop_column("editorial_post", "cover_bytes")
