"""Merge database rule overrides onto the shipped YAML pack and publish them.

The merge is by rule ID: an override with a YAML rule's ID replaces it, an
override with a new ID adds a rule, and a disabled row suppresses the YAML rule.
Wholesale replacement was rejected because it would force an operator to
re-enter the entire baseline pack before adding a single keyword.
"""

from __future__ import annotations

from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.engine.rules import matching_patterns
from app.engine.rules.loader import (
    RuleDefinition,
    RulePack,
    load_yaml_rule_pack,
    set_active_rule_pack,
)
from app.obs.events import log_error, log_event
from app.rules_store.repo import RuleOverrideDraft, load_overrides


def preview_rule(draft: RuleOverrideDraft, sample: str) -> tuple[str, ...]:
    """Return the patterns in ``draft`` that would fire on ``sample``.

    The operator dry-run: a bad pattern here degrades detection silently for
    every user, and ``main`` deploys on merge, so an edit must be testable
    before it is saved. Raises ``ValueError`` if the draft itself is invalid.
    """

    normalized = draft.normalized()
    rule = RuleDefinition(
        id=normalized.rule_id,
        family=normalized.family,
        desc=normalized.description,
        message_key=normalized.message_key,
        severity=normalized.severity,
        match={language: tuple(values) for language, values in normalized.patterns.items()},
        emits_signal=normalized.emits_signal,
    )
    return matching_patterns(rule, sample)


def merge_rule_pack(
    base: RulePack,
    overrides: tuple[RuleDefinition, ...],
    disabled: frozenset[str],
) -> RulePack:
    """Overlay ``overrides`` onto ``base`` by rule ID, preserving pack order."""

    by_id = {rule.id: rule for rule in overrides}
    merged: list[RuleDefinition] = []
    for rule in base.rules:
        if rule.id in disabled:
            continue
        merged.append(by_id.pop(rule.id, rule))
    # Whatever is left introduces a rule the YAML baseline does not define.
    merged.extend(rule for rule in by_id.values() if rule.id not in disabled)

    return RulePack(
        rules=tuple(merged),
        descriptions={rule.id: rule.desc for rule in merged},
    )


async def refresh_rule_pack(session: AsyncSession) -> RulePack:
    """Merge the stored overrides onto the YAML baseline and publish the result."""

    base = load_yaml_rule_pack()
    overrides, disabled = await load_overrides(session)
    merged = merge_rule_pack(base, overrides, disabled)
    set_active_rule_pack(merged)
    log_event(
        "rule_pack_refreshed",
        baseline_rules=len(base.rules),
        override_rules=len(overrides),
        disabled_rules=len(disabled),
        active_rules=len(merged.rules),
    )
    return merged


async def run_rule_pack_refresh_job(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Refresh the pack, leaving the previous one in force on failure."""

    try:
        async with session_factory() as session:
            await refresh_rule_pack(session)
    except Exception as exc:
        # Never propagate into the scheduler: the pack already in force
        # (merged or YAML baseline) keeps serving checks.
        log_error(stage="rule_pack", error_type=type(exc).__name__)


def install_rule_pack_refresh_job(
    scheduler: AsyncIOScheduler,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    """Install the periodic rule-pack refresh on the existing in-process scheduler."""

    scheduler.add_job(
        run_rule_pack_refresh_job,
        "interval",
        args=[session_factory],
        minutes=settings.rule_pack_refresh_minutes,
        next_run_time=datetime.now(UTC),
        id="rule_pack_refresh",
        replace_existing=True,
    )
