"""Drop the retired Uzbek Cyrillic columns from editorial posts.

Uzbek Cyrillic is no longer a reply language: cases are authored and served in
``uz_latn`` and ``ru`` only. The three ``*_uz_cyrl`` columns were left dormant
when the language was retired so the existing NOT NULL constraints stayed
satisfiable; this removes them.

This drops data. Any Cyrillic case text authored before the retirement is lost,
which is why it ships separately from the language removal itself rather than
alongside it.

The downgrade restores the columns as NOT NULL with an empty-string server
default, so the schema round-trips even though the original text cannot.

Revision ID: 0008_drop_editorial_uz_cyrl
Revises: 0007_drop_face
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_drop_editorial_uz_cyrl"
down_revision: str | None = "0007_drop_face"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = ("title_uz_cyrl", "summary_uz_cyrl", "article_uz_cyrl")


def upgrade() -> None:
    for column in _COLUMNS:
        op.drop_column("editorial_post", column)


def downgrade() -> None:
    for column in _COLUMNS:
        op.add_column(
            "editorial_post",
            sa.Column(column, sa.Text(), nullable=False, server_default=""),
        )
        op.alter_column("editorial_post", column, server_default=None)
