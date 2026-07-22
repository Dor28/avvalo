"""Operator-authored editorial content stored outside the user-data schema.

Editorial posts are written manually by an authenticated founder. They are
never populated from checks, OCR, model output, or legacy story submissions.
Keeping their metadata on a separate declarative base makes that boundary
explicit and preserves the zero-content contract of ``app.data.models.Base``.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class EditorialBase(DeclarativeBase):
    """Declarative base for operator-authored public content only."""


class EditorialPost(EditorialBase):
    """A trilingual case article authored and controlled by an operator."""

    __tablename__ = "editorial_post"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    title_uz_latn: Mapped[str] = mapped_column(Text, nullable=False)
    summary_uz_latn: Mapped[str] = mapped_column(Text, nullable=False)
    article_uz_latn: Mapped[str] = mapped_column(Text, nullable=False)
    title_uz_cyrl: Mapped[str] = mapped_column(Text, nullable=False)
    summary_uz_cyrl: Mapped[str] = mapped_column(Text, nullable=False)
    article_uz_cyrl: Mapped[str] = mapped_column(Text, nullable=False)
    title_ru: Mapped[str] = mapped_column(Text, nullable=False)
    summary_ru: Mapped[str] = mapped_column(Text, nullable=False)
    article_ru: Mapped[str] = mapped_column(Text, nullable=False)

    created_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    published_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
