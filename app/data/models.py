"""SQLAlchemy ORM models for Avvalo's privacy-safe schema (§5.2).

Hard rule: **no table stores submitted content** — not text, OCR text, model
output, URLs, names, usernames, or file ids. Only pseudonymous keys, categorical
fields, rule IDs, and metrics live here. The companion test asserts this by
inspecting the metadata, so adding a content-like column will fail the build.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    ARRAY,
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    false,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# rule_ids is a Postgres TEXT[] in production; SQLite (unit tests only) has no
# array type, so it falls back to JSON there. Production DDL uses the array.
RULE_IDS_TYPE = ARRAY(Text).with_variant(JSON, "sqlite")


class Base(DeclarativeBase):
    """Declarative base carrying the shared metadata."""


class Consent(Base):
    """One row per (user, face): proof the privacy notice was accepted."""

    __tablename__ = "consent"

    user_key: Mapped[str] = mapped_column(Text, primary_key=True)
    face: Mapped[str] = mapped_column(Text, primary_key=True)
    notice_version: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CheckEvent(Base):
    """A privacy-safe record of one check. Carries IDs and metrics, never text."""

    __tablename__ = "check_event"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_key: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    face: Mapped[str] = mapped_column(Text, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    input_type: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False)
    rule_ids: Mapped[list[str]] = mapped_column(RULE_IDS_TYPE, nullable=False, default=list)
    knowledge_card_ids: Mapped[list[str]] = mapped_column(
        RULE_IDS_TYPE, nullable=False, default=list
    )
    reviewed_case_ids: Mapped[list[str]] = mapped_column(
        RULE_IDS_TYPE, nullable=False, default=list
    )
    retrieval_mode: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrieval_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    router_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    kb_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    no_signal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error_class: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ocr_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    safety_blocked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )


class Feedback(Base):
    """Categorical post-check feedback, keyed to the check it answers."""

    __tablename__ = "feedback"

    check_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    usefulness: Mapped[str] = mapped_column(Text, nullable=False)
    next_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RateLimit(Base):
    """Per (user, face, day) check counter backing the daily limit."""

    __tablename__ = "rate_limit"

    user_key: Mapped[str] = mapped_column(Text, primary_key=True)
    face: Mapped[str] = mapped_column(Text, primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class DeletionLog(Base):
    """Audit trail for /delete_my_data requests.

    The spec lists (user_key, requested_ts, completed_ts); a surrogate ``id`` is
    added so the ORM has a primary key and a user may appear more than once.
    """

    __tablename__ = "deletion_log"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_key: Mapped[str] = mapped_column(Text, nullable=False)
    requested_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StorySubmission(Base):
    """Opt-in minimized story awaiting founder review.

    This is the one R3 exception to the no-content schema rule:
    ``minimized_text`` may store only the minimizer's derivative, never raw
    user-submitted text.
    """

    __tablename__ = "story_submission"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_key: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    face: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False)
    minimized_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="submitted")
    created_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class URLBlocklist(Base):
    """Hash-only local reputation entry sourced from a public feed."""

    __tablename__ = "url_blocklist"

    domain_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(40), primary_key=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
