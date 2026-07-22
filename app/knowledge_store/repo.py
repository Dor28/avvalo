"""Validated persistence for operator-authored knowledge cards.

Every write is validated before it reaches the database because a malformed card
changes what the answer model is told. A card that cannot be validated at *load*
time is skipped rather than raised: one bad row must not drop the whole
knowledge base back to its YAML baseline.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.faces import FACES
from app.engine.knowledge.types import KnowledgeCard
from app.knowledge_store.models import KnowledgeCardOverride

LANGUAGES = ("uz_latn", "uz_cyrl", "ru")
STATUSES = ("approved", "draft", "retired")
CARD_ID_RE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+$")
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,39}$")
RULE_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z0-9_]+)+$")
SIGNAL_KIND_RE = re.compile(r"^[a-z][a-z0-9_]*$")
REVIEWER_MAX_CHARS = 120
MECHANISM_MAX_CHARS = 600
ENTRY_MAX_CHARS = 400
MAX_ENTRIES = 12
ALIAS_MAX_CHARS = 120
MAX_ALIASES_PER_LANGUAGE = 40


@dataclass(frozen=True)
class LoadedOverrides:
    """The result of reading one face's card overrides."""

    approved: tuple[KnowledgeCard, ...]
    suppressed_ids: frozenset[str]
    latest_updated_ts: datetime | None


class KnowledgeCardDraft(BaseModel):
    """Validated values accepted from the operator-only card editor."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    face: str
    card_id: str
    card_version: str
    status: str
    reviewer: str
    mechanism: str
    trigger_rule_ids: list[str] = []
    trigger_signal_kinds: list[str] = []
    retrieval_aliases: dict[str, list[str]] = {}
    red_flags: list[str] = []
    verify_steps: list[str] = []
    questions: list[str] = []
    reviewed_case_ids: list[str] = []

    def normalized(self) -> KnowledgeCardDraft:
        """Strip whitespace and reject anything retrieval or the prompt cannot use."""

        if self.face not in FACES:
            raise ValueError("invalid_face")
        card_id = self.card_id.strip().casefold()
        if not CARD_ID_RE.fullmatch(card_id):
            raise ValueError("invalid_card_id")
        card_version = self.card_version.strip()
        if not VERSION_RE.fullmatch(card_version):
            raise ValueError("invalid_card_version")
        if self.status not in STATUSES:
            raise ValueError("invalid_status")
        reviewer = self.reviewer.strip()
        if not reviewer or len(reviewer) > REVIEWER_MAX_CHARS:
            raise ValueError("invalid_reviewer")
        mechanism = self.mechanism.strip()
        if not mechanism or len(mechanism) > MECHANISM_MAX_CHARS:
            raise ValueError("invalid_mechanism")

        trigger_rule_ids = _validate_ids(self.trigger_rule_ids, RULE_ID_RE, "invalid_trigger_rule")
        trigger_signal_kinds = _validate_ids(
            self.trigger_signal_kinds, SIGNAL_KIND_RE, "invalid_trigger_signal"
        )
        reviewed_case_ids = _validate_ids(
            self.reviewed_case_ids, CARD_ID_RE, "invalid_reviewed_case"
        )

        return KnowledgeCardDraft(
            face=self.face,
            card_id=card_id,
            card_version=card_version,
            status=self.status,
            reviewer=reviewer,
            mechanism=mechanism,
            trigger_rule_ids=trigger_rule_ids,
            trigger_signal_kinds=trigger_signal_kinds,
            retrieval_aliases=_validate_aliases(self.retrieval_aliases),
            red_flags=_validate_entries(self.red_flags, "invalid_red_flags"),
            verify_steps=_validate_entries(self.verify_steps, "invalid_verify_steps"),
            questions=_validate_entries(self.questions, "invalid_questions"),
            reviewed_case_ids=reviewed_case_ids,
        )

    def as_card(self) -> KnowledgeCard:
        """Project a validated draft onto the engine's card contract."""

        values = self.normalized()
        return KnowledgeCard(
            id=values.card_id,
            face=values.face,
            version=values.card_version,
            status=values.status,
            reviewer=values.reviewer,
            trigger_rule_ids=values.trigger_rule_ids,
            trigger_signal_kinds=values.trigger_signal_kinds,
            retrieval_aliases=values.retrieval_aliases,
            mechanism=values.mechanism,
            red_flags=values.red_flags,
            verify_steps=values.verify_steps,
            questions=values.questions,
            reviewed_case_ids=values.reviewed_case_ids,
        )


def _validate_entries(values: list[str], error: str) -> list[str]:
    if not isinstance(values, list) or len(values) > MAX_ENTRIES:
        raise ValueError(error)
    entries = [str(value).strip() for value in values]
    entries = [entry for entry in entries if entry]
    if any(len(entry) > ENTRY_MAX_CHARS for entry in entries):
        raise ValueError(error)
    return entries


def _validate_ids(values: list[str], pattern: re.Pattern[str], error: str) -> list[str]:
    if not isinstance(values, list) or len(values) > MAX_ENTRIES:
        raise ValueError(error)
    entries = [str(value).strip().casefold() for value in values]
    entries = [entry for entry in entries if entry]
    if any(not pattern.fullmatch(entry) for entry in entries):
        raise ValueError(error)
    return entries


def _validate_aliases(raw: dict[str, list[str]]) -> dict[str, list[str]]:
    if not isinstance(raw, dict):
        raise ValueError("invalid_aliases")
    cleaned: dict[str, list[str]] = {}
    for language, values in raw.items():
        if language not in LANGUAGES:
            raise ValueError("invalid_alias_language")
        if not isinstance(values, list) or len(values) > MAX_ALIASES_PER_LANGUAGE:
            raise ValueError("invalid_aliases")
        entries = [str(value).strip() for value in values]
        entries = [entry for entry in entries if entry]
        if any(len(entry) > ALIAS_MAX_CHARS for entry in entries):
            raise ValueError("invalid_aliases")
        cleaned[language] = entries
    return cleaned


async def create_card(session: AsyncSession, draft: KnowledgeCardDraft) -> KnowledgeCardOverride:
    """Create one validated card override and flush it."""

    values = draft.normalized()
    now = datetime.now(UTC)
    override = KnowledgeCardOverride(
        id=uuid.uuid4(),
        **values.__dict__,
        created_ts=now,
        updated_ts=now,
    )
    session.add(override)
    await session.flush()
    return override


async def update_card(
    session: AsyncSession,
    override: KnowledgeCardOverride,
    draft: KnowledgeCardDraft,
) -> KnowledgeCardOverride:
    """Replace editable values on an existing card override."""

    values = draft.normalized()
    for field, value in values.__dict__.items():
        setattr(override, field, value)
    override.updated_ts = datetime.now(UTC)
    await session.flush()
    return override


async def get_card(
    session: AsyncSession, override_id: uuid.UUID
) -> KnowledgeCardOverride | None:
    """Return one card override regardless of status."""

    return await session.get(KnowledgeCardOverride, override_id)


async def delete_card(session: AsyncSession, override: KnowledgeCardOverride) -> None:
    """Remove an override so the shipped YAML card applies again."""

    await session.delete(override)
    await session.flush()


async def list_cards(
    session: AsyncSession, *, face: str | None = None
) -> list[KnowledgeCardOverride]:
    """Return card overrides for the editor, newest change first."""

    statement = select(KnowledgeCardOverride).order_by(KnowledgeCardOverride.updated_ts.desc())
    if face is not None:
        statement = statement.where(KnowledgeCardOverride.face == face)
    return list((await session.execute(statement)).scalars())


async def load_overrides(session: AsyncSession, *, face: str) -> LoadedOverrides:
    """Return approved override cards, suppressed IDs, and the newest change time.

    A row that fails validation is skipped rather than raised, so one bad card
    cannot drop the whole base to its YAML baseline.
    """

    rows = await list_cards(session, face=face)
    approved: list[KnowledgeCard] = []
    suppressed: set[str] = set()
    latest: datetime | None = None

    for row in rows:
        try:
            card = _card_from_row(row)
        except (ValueError, TypeError):
            continue
        latest = row.updated_ts if latest is None else max(latest, row.updated_ts)
        if card.status == "approved":
            approved.append(card)
        else:
            # draft/retired suppress the shipped card of the same ID.
            suppressed.add(card.id)

    return LoadedOverrides(
        approved=tuple(approved),
        suppressed_ids=frozenset(suppressed),
        latest_updated_ts=latest,
    )


def _card_from_row(row: KnowledgeCardOverride) -> KnowledgeCard:
    draft = KnowledgeCardDraft(
        face=row.face,
        card_id=row.card_id,
        card_version=row.card_version,
        status=row.status,
        reviewer=row.reviewer,
        mechanism=row.mechanism,
        trigger_rule_ids=list(row.trigger_rule_ids or []),
        trigger_signal_kinds=list(row.trigger_signal_kinds or []),
        retrieval_aliases=dict(row.retrieval_aliases or {}),
        red_flags=list(row.red_flags or []),
        verify_steps=list(row.verify_steps or []),
        questions=list(row.questions or []),
        reviewed_case_ids=list(row.reviewed_case_ids or []),
    )
    return draft.as_card()
