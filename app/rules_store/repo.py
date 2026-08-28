"""Validated persistence for operator-authored rule overrides.

Every write is validated before it reaches the database because a malformed
pattern degrades detection silently for every user: an uncompilable regex would
raise inside the matcher, and an over-broad one would fire on all content.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.rules.loader import (
    MATCH_MODE_SUBSTRING,
    MATCH_MODES,
    RuleDefinition,
    RuleRequirement,
)
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
# Co-occurrence gate (PIPELINE_V2 §6): rule IDs in any_of/all_of, signal kinds
# in signals. A gate longer than this is a rule that should be split.
REQUIRES_KEYS = ("any_of", "all_of", "signals")
MAX_REQUIRES_ENTRIES = 20


class RuleOverrideDraft(BaseModel):
    """Validated values accepted from the operator-only rule editor."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    family: str
    description: str
    message_key: str
    severity: int
    emits_signal: str | None = None
    patterns: dict[str, list[str]]
    # Optional precision controls; omitting them reproduces the historical
    # behavior exactly (no exclusions, substring matching, no gate).
    exclude: dict[str, list[str]] = Field(default_factory=dict)
    match_mode: str = MATCH_MODE_SUBSTRING
    requires: dict[str, list[str]] | None = None
    disabled: bool = False

    def normalized(self) -> RuleOverrideDraft:
        """Strip whitespace and reject anything that would break the matcher."""

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
            rule_id=rule_id,
            family=family,
            description=description,
            message_key=message_key,
            severity=self.severity,
            emits_signal=emits_signal,
            patterns=patterns,
            exclude=_validate_exclude(self.exclude),
            match_mode=_validate_match_mode(self.match_mode),
            requires=_validate_requires(self.requires),
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


def _validate_exclude(raw: dict[str, list[str]] | None) -> dict[str, list[str]]:
    """Validate the optional exclusion groups; absent means "no exclusions"."""

    if not raw:
        return {}
    return _validate_patterns(raw)


def _validate_match_mode(raw: str | None) -> str:
    mode = (raw or "").strip().casefold() or MATCH_MODE_SUBSTRING
    if mode not in MATCH_MODES:
        raise ValueError("invalid_match_mode")
    return mode


def _validate_requires(raw: dict[str, list[str]] | None) -> dict[str, list[str]] | None:
    """Validate the optional co-occurrence gate; absent means "no gate".

    A gate written with keys but no entries is rejected rather than dropped: it
    reads as a restriction while restricting nothing, which is how an operator
    ends up shipping a broad keyword they believed was gated.
    """

    if not raw:
        return None
    if not isinstance(raw, dict):
        raise ValueError("invalid_requires")

    cleaned: dict[str, list[str]] = {}
    for key, values in raw.items():
        if key not in REQUIRES_KEYS:
            raise ValueError("invalid_requires")
        if not isinstance(values, list) or len(values) > MAX_REQUIRES_ENTRIES:
            raise ValueError("invalid_requires")
        expected = MESSAGE_KEY_RE if key == "signals" else RULE_ID_RE
        entries = [str(value).strip().casefold() for value in values]
        entries = [entry for entry in entries if entry]
        if any(not expected.fullmatch(entry) for entry in entries):
            raise ValueError("invalid_requires")
        cleaned[key] = entries

    if not any(cleaned.values()):
        raise ValueError("invalid_requires")
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


async def list_overrides(session: AsyncSession) -> list[RuleOverride]:
    """Return overrides for the editor, newest change first."""

    statement = select(RuleOverride).order_by(RuleOverride.updated_ts.desc())
    return list((await session.execute(statement)).scalars())


async def load_overrides(
    session: AsyncSession,
) -> tuple[tuple[RuleDefinition, ...], frozenset[str]]:
    """Return active override definitions and the rule IDs to suppress.

    A row that fails validation is skipped rather than raised: one bad row must
    not take the whole pack down to its YAML baseline.
    """

    rows = await list_overrides(session)
    definitions: list[RuleDefinition] = []
    disabled: set[str] = set()
    for row in rows:
        if row.disabled:
            disabled.add(row.rule_id)
            continue
        try:
            patterns = _validate_patterns(row.patterns)
            exclude = _validate_exclude(row.exclude)
            match_mode = _validate_match_mode(row.match_mode)
            requires = _validate_requires(row.requires)
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
                exclude={language: tuple(values) for language, values in exclude.items()},
                match_mode=match_mode,
                requires=RuleRequirement.from_mapping(requires),
            )
        )
    return tuple(definitions), frozenset(disabled)
