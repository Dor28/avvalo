"""Operator-authored rule overrides stored outside the user-data schema.

Rule overrides are keyword and regex patterns written by an authenticated
operator. They are reference data about scam *language*, never user content, so
they sit on their own declarative base — the same boundary
``app.content.models.EditorialBase`` draws — and stay out of the zero-content
contract enforced over ``app.data.models.Base`` by ``tests/test_schema_privacy``.

Keeping patterns here rather than in the public repository means new keyword
work is not published to attackers; the shipped YAML pack remains the
fallback baseline (V1_TECHNICAL_PLAN §5).
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, Text, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class RuleStoreBase(DeclarativeBase):
    """Declarative base for operator-authored detection patterns only."""


class RuleOverride(RuleStoreBase):
    """One rule that overrides, adds to, or disables a YAML pack rule by ID."""

    __tablename__ = "rule_override"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    rule_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)

    family: Mapped[str] = mapped_column(Text, nullable=False)
    # Neutral-English meaning handed to the LLM as a grounded fact.
    description: Mapped[str] = mapped_column(Text, nullable=False)
    message_key: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[int] = mapped_column(Integer, nullable=False)
    emits_signal: Mapped[str | None] = mapped_column(Text, nullable=True)
    # {"uz_latn": [...], "uz_cyrl": [...], "ru": [...]} — patterns, not user data.
    patterns: Mapped[dict[str, list[str]]] = mapped_column(JSON, nullable=False, default=dict)

    # A disabled row suppresses the same rule ID in the shipped YAML pack.
    disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
