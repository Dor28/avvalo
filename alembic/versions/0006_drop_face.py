"""Drop the retired product-face discriminator.

Avvalo has exactly one consumer check surface, so ``face`` no longer identifies
anything: every row carries the literal ``'family'``. The column is removed from
``check_event`` and ``story_submission``, and dropped from the ``consent``
primary key.

``rate_limit`` is the one place where ``face`` was doing real work: the web
channel stored its per-IP counter under a synthetic ``'web_ip:family'`` face to
keep those rows from colliding with per-user rows. That separation is preserved
as an explicit ``scope`` column (``'user'`` / ``'web_ip'``), which is what the
field always meant.

Revision ID: 0006_drop_face
Revises: 0005_improvement_backlog
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_drop_face"
down_revision: str | None = "0005_improvement_backlog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── consent: (user_key, face) -> (user_key) ────────────────────────────────
    # Only one face was ever written, so at most one row per user exists in
    # practice. Collapse defensively anyway: keep the newest row per user_key so
    # a live user is never forced to re-consent by this migration.
    op.execute(
        sa.text(
            """
            DELETE FROM consent a
            USING consent b
            WHERE a.user_key = b.user_key
              AND (a.ts, a.face) < (b.ts, b.face)
            """
        )
    )
    op.drop_constraint("consent_pkey", "consent", type_="primary")
    op.drop_column("consent", "face")
    op.create_primary_key("consent_pkey", "consent", ["user_key"])

    # ── rate_limit: face -> scope ─────────────────────────────────────────────
    op.add_column(
        "rate_limit",
        sa.Column("scope", sa.Text(), nullable=False, server_default="user"),
    )
    op.execute(
        sa.text(
            """
            UPDATE rate_limit
            SET scope = CASE
                WHEN face LIKE 'web\\_ip:%' THEN 'web_ip'
                ELSE 'user'
            END
            """
        )
    )
    # Counters are day-scoped and self-heal within 24h, so an unexpected
    # collision after the collapse is merged rather than allowed to break the PK.
    op.execute(
        sa.text(
            """
            DELETE FROM rate_limit a
            USING rate_limit b
            WHERE a.user_key = b.user_key
              AND a.day = b.day
              AND a.scope = b.scope
              AND a.face > b.face
            """
        )
    )
    op.drop_constraint("rate_limit_pkey", "rate_limit", type_="primary")
    op.drop_column("rate_limit", "face")
    op.create_primary_key("rate_limit_pkey", "rate_limit", ["user_key", "scope", "day"])
    op.alter_column("rate_limit", "scope", server_default=None)

    # ── plain drops ───────────────────────────────────────────────────────────
    op.drop_column("check_event", "face")
    op.drop_column("story_submission", "face")


def downgrade() -> None:
    op.add_column(
        "story_submission",
        sa.Column("face", sa.Text(), nullable=False, server_default="family"),
    )
    op.alter_column("story_submission", "face", server_default=None)
    op.add_column(
        "check_event",
        sa.Column("face", sa.Text(), nullable=False, server_default="family"),
    )
    op.alter_column("check_event", "face", server_default=None)

    op.add_column(
        "rate_limit",
        sa.Column("face", sa.Text(), nullable=False, server_default="family"),
    )
    op.execute(
        sa.text(
            """
            UPDATE rate_limit
            SET face = CASE
                WHEN scope = 'web_ip' THEN 'web_ip:family'
                ELSE 'family'
            END
            """
        )
    )
    op.drop_constraint("rate_limit_pkey", "rate_limit", type_="primary")
    op.drop_column("rate_limit", "scope")
    op.create_primary_key("rate_limit_pkey", "rate_limit", ["user_key", "face", "day"])
    op.alter_column("rate_limit", "face", server_default=None)

    op.add_column(
        "consent",
        sa.Column("face", sa.Text(), nullable=False, server_default="family"),
    )
    op.drop_constraint("consent_pkey", "consent", type_="primary")
    op.create_primary_key("consent_pkey", "consent", ["user_key", "face"])
    op.alter_column("consent", "face", server_default=None)
