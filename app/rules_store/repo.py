"""Validated persistence for operator-authored rule overrides.

Every write is validated before it reaches the database because a malformed
pattern degrades detection silently for every user: an uncompilable regex would
raise inside the matcher, and an over-broad one would fire on all content.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.faces import FACES
from app.engine.rules.loader import RuleDefinition
from app.rules_store.models import RuleOverride

LANGUAGES = ("uz_latn", "uz_cyrl", "ru")
RULE_ID_RE = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z0-9_]+)+$")
FAMILY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
MESSAGE_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
SEVERITY_RANGE = (1, 3)
DESCRIPTION_MAX_CHARS = 400
PATTERN_MAX_CHARS = 120
MAX_PATTERNS_PER_LANGUAGE = 60
REGEX_PREFIX = "regex:"
# A literal shorter than this matches far too much text to be a useful signal.
MIN_LITERAL_CHARS = 3


class RuleOverrideDraft(BaseModel):
    """Validated values accepted from the operator-only rule editor."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    face: str
    rule_id: str
    family: str
    description: str
    message_key: str
    severity: int
    emits_signal: str | None = None
    patterns: dict[str, list[str]]
    disabled: bool = False

    def normalized(self) -> RuleOverrideDraft:
        """Strip whitespace and reject anything that would break the matcher."""

        if self.face not in FACES:
            raise ValueError("invalid_face")
        rule_id = self.rule_id.strip().casefold()
        if not RULE_ID_RE.fullmatch(rule_id):
            raise ValueError("invalid_rule_id")
        family = self.family.strip().casefold()
        if not FAMILY_RE.fullmatch(family):
            raise ValueError("invalid_family")
        message_key = self.message_key.strip().casefold()
        if not MESSAGE_KEY_RE.fullmatch(message_key):
            raise ValueError("invalid_message_key")
        description = self.description.strip()
        if not description or len(description) > DESCRIPTION_MAX_CHARS:
            raise ValueError("invalid_description")
        if not SEVERITY_RANGE[0] <= self.severity <= SEVERITY_RANGE[1]:
            raise ValueError("invalid_severity")

        emits_signal = (self.emits_signal or "").strip().casefold() or None
        if emits_signal is not None and not MESSAGE_KEY_RE.fullmatch(emits_signal):
            raise ValueError("invalid_emits_signal")

        patterns = _validate_patterns(self.patterns)
        # A disabled row only needs its ID to suppress the YAML rule, but it
        # still carries valid fields so re-enabling it cannot resurrect junk.
        if not self.disabled and not any(patterns.values()):
            raise ValueError("no_patterns")

        return RuleOverrideDraft(
            face=self.face,
            rule_id=rule_id,
            family=family,
            description=description,
            message_key=message_key,
            severity=self.severity,
            emits_signal=emits_signal,
            patterns=patterns,
            disabled=self.disabled,
        )


def _validate_patterns(raw: dict[str, list[str]]) -> dict[str, list[str]]:
    if not isinstance(raw, dict) or not raw:
        raise ValueError("invalid_patterns")

    cleaned: dict[str, list[str]] = {}
    for language, values in raw.items():
        if language not in LANGUAGES:
            raise ValueError("invalid_pattern_language")
        if not isinstance(values, list) or len(values) > MAX_PATTERNS_PER_LANGUAGE:
            raise ValueError("invalid_patterns")
        entries = [str(value).strip() for value in values]
        cleaned[language] = [_validate_pattern(entry) for entry in entries if entry]
    return cleaned


def _validate_pattern(pattern: str) -> str:
    if len(pattern) > PATTERN_MAX_CHARS:
        raise ValueError("pattern_too_long")
    if pattern.casefold().startswith(REGEX_PREFIX):
        expression = pattern[len(REGEX_PREFIX) :].strip()
        if not expression:
            raise ValueError("empty_regex")
        try:
            re.compile(expression)
        except re.error as exc:
            raise ValueError("invalid_regex") from exc
        return f"{REGEX_PREFIX}{expression}"
    if len(pattern) < MIN_LITERAL_CHARS:
        raise ValueError("pattern_too_short")
    return pattern


async def create_override(session: AsyncSession, draft: RuleOverrideDraft) -> RuleOverride:
    """Create one validated override and flush it."""

    values = draft.normalized()
    now = datetime.now(UTC)
    override = RuleOverride(
        id=uuid.uuid4(),
        **values.__dict__,
        created_ts=now,
        updated_ts=now,
    )
    session.add(override)
    await session.flush()
    return override


async def update_override(
    session: AsyncSession,
    override: RuleOverride,
    draft: RuleOverrideDraft,
) -> RuleOverride:
    """Replace editable values on an existing override."""

    values = draft.normalized()
    for field, value in values.__dict__.items():
        setattr(override, field, value)
    override.updated_ts = datetime.now(UTC)
    await session.flush()
    return override


async def get_override(session: AsyncSession, override_id: uuid.UUID) -> RuleOverride | None:
    """Return one override regardless of its disabled state."""

    return await session.get(RuleOverride, override_id)


async def delete_override(session: AsyncSession, override: RuleOverride) -> None:
    """Remove an override so the shipped YAML rule applies again."""

    await session.delete(override)
    await session.flush()


async def list_overrides(session: AsyncSession, *, face: str | None = None) -> list[RuleOverride]:
    """Return overrides for the editor, newest change first."""

    statement = select(RuleOverride).order_by(RuleOverride.updated_ts.desc())
    if face is not None:
        statement = statement.where(RuleOverride.face == face)
    return list((await session.execute(statement)).scalars())


async def load_overrides(
    session: AsyncSession, *, face: str
) -> tuple[tuple[RuleDefinition, ...], frozenset[str]]:
    """Return active override definitions and the rule IDs to suppress.

    A row that fails validation is skipped rather than raised: one bad row must
    not take the whole pack down to its YAML baseline.
    """

    rows = await list_overrides(session, face=face)
    definitions: list[RuleDefinition] = []
    disabled: set[str] = set()
    for row in rows:
        if row.disabled:
            disabled.add(row.rule_id)
            continue
        try:
            patterns = _validate_patterns(row.patterns)
        except ValueError:
            continue
        if not any(patterns.values()):
            continue
        definitions.append(
            RuleDefinition(
                id=row.rule_id,
                family=row.family,
                desc=row.description,
                message_key=row.message_key,
                severity=row.severity,
                match={language: tuple(values) for language, values in patterns.items()},
                emits_signal=row.emits_signal,
            )
        )
    return tuple(definitions), frozenset(disabled)
