"""Operator-authored knowledge cards stored outside the user-data schema.

Cards are reviewed guidance written by an authenticated operator and handed to
the answer model as explanatory context. Like ``EditorialBase`` and
``RuleStoreBase`` they sit on their own declarative base: they are reference
data, never user content, and must stay outside the zero-content contract that
``tests/test_schema_privacy`` enforces over ``app.data.models.Base``.

Keeping cards here rather than in the public repository means new card work is
not published on push; ``knowledge/<face>/cards.yaml`` remains the fallback
baseline (AI_KNOWLEDGE_PIPELINE §6).
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class KnowledgeStoreBase(DeclarativeBase):
    """Declarative base for operator-authored knowledge cards only."""


class KnowledgeCardOverride(KnowledgeStoreBase):
    """One card that overrides, adds to, or suppresses a YAML baseline card."""

    __tablename__ = "knowledge_card_override"
    __table_args__ = (
        UniqueConstraint("face", "card_id", name="uq_knowledge_card_override_face_card"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    face: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    card_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)

    card_version: Mapped[str] = mapped_column(Text, nullable=False)
    # approved | draft | retired — only ``approved`` ever reaches retrieval.
    status: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    reviewer: Mapped[str] = mapped_column(Text, nullable=False)

    trigger_rule_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    trigger_signal_kinds: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    # {"uz_latn": [...], "uz_cyrl": [...], "ru": [...]} — recall cues, not user data.
    retrieval_aliases: Mapped[dict[str, list[str]]] = mapped_column(
        JSON, nullable=False, default=dict
    )

    # Card bodies are English: they are handed to the model as guidance and
    # never shown to a user verbatim.
    mechanism: Mapped[str] = mapped_column(Text, nullable=False)
    red_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    verify_steps: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    questions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    reviewed_case_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    created_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
