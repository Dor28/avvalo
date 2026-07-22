"""Privacy-safe metrics aggregation for the pitch/demo surface."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.models import CheckEvent, Consent, Feedback
from app.engine.knowledge import FileKnowledgeStore, KnowledgeLookupError, KnowledgeStore

COMPLETED_STATUSES = {"ok", "no_signal"}


async def collect_metrics(
    session: AsyncSession,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    knowledge_store: KnowledgeStore | None = None,
) -> dict[str, Any]:
    """Return aggregate-only operational metrics.

    The result intentionally contains no user keys, check IDs, text, OCR text,
    prompts, model outputs, links, phone numbers, or file identifiers.
    """

    since = _normalize_bound(since)
    until = _normalize_bound(until)
    event_conditions = _event_window(since=since, until=until)
    consent_conditions = _consent_window(since=since, until=until)

    total_checks = await _count_events(session, event_conditions)
    completed_checks = await _count_events(
        session,
        [*event_conditions, CheckEvent.status.in_(COMPLETED_STATUSES)],
    )
    no_signal_count = await _count_events(
        session,
        [*event_conditions, CheckEvent.no_signal.is_(True)],
    )
    safety_blocked = await _count_events(
        session,
        [*event_conditions, CheckEvent.safety_blocked.is_(True)],
    )
    activated_users = await _scalar_int(
        session,
        select(func.count(distinct(CheckEvent.user_key))).where(
            *event_conditions,
            CheckEvent.status.in_(COMPLETED_STATUSES),
        ),
    )
    consented_users = await _scalar_int(
        session,
        select(func.count(distinct(Consent.user_key))).where(*consent_conditions),
    )
    total_cost = await _decimal_sum(session, CheckEvent.cost_usd, event_conditions)
    completed_cost = await _decimal_sum(
        session,
        CheckEvent.cost_usd,
        [*event_conditions, CheckEvent.status.in_(COMPLETED_STATUSES)],
    )
    average_latency = await _scalar_float(
        session,
        select(func.avg(CheckEvent.latency_ms)).where(*event_conditions),
    )

    knowledge = await _knowledge_metrics(session, event_conditions)
    knowledge["inventory"] = collect_knowledge_inventory(
        knowledge_store or FileKnowledgeStore()
    )
    return {
        "window": {
            "since": since.isoformat() if since else None,
            "until": until.isoformat() if until else None,
        },
        "checks": {
            "total": total_checks,
            "completed": completed_checks,
            "failed": max(0, total_checks - completed_checks),
            "completion_rate": _rate(completed_checks, total_checks),
        },
        "activation": {
            "consented_users": consented_users,
            "activated_users": activated_users,
            "activation_rate": _rate(activated_users, consented_users),
        },
        "cost": {
            "total_usd": _round_money(total_cost),
            "avg_success_usd": _round_money(
                completed_cost / completed_checks if completed_checks else Decimal("0")
            ),
        },
        "latency": {
            "avg_ms": round(average_latency, 2) if average_latency is not None else None,
        },
        "no_signal": {
            "count": no_signal_count,
            "rate": _rate(no_signal_count, completed_checks),
        },
        "safety": {
            "blocked": safety_blocked,
        },
        "breakdowns": {
            "status": await _breakdown(session, CheckEvent.status, event_conditions),
            "language": await _breakdown(session, CheckEvent.language, event_conditions),
        },
        "feedback": {
            "usefulness": await _feedback_breakdown(
                session, Feedback.usefulness, since=since, until=until
            ),
            "next_action": await _feedback_breakdown(
                session,
                Feedback.next_action,
                since=since,
                until=until,
                exclude_null=True,
            ),
        },
        "knowledge": knowledge,
    }


async def export_metrics(
    session: AsyncSession,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
) -> str:
    """Return a compact text export suitable for an operator CLI."""

    summary = await collect_metrics(session, since=since, until=until)
    lines = [
        f"checks_total={summary['checks']['total']}",
        f"checks_completed={summary['checks']['completed']}",
        f"completion_rate={summary['checks']['completion_rate']}",
        f"activated_users={summary['activation']['activated_users']}",
        f"activation_rate={summary['activation']['activation_rate']}",
        f"cost_total_usd={summary['cost']['total_usd']}",
        f"cost_avg_success_usd={summary['cost']['avg_success_usd']}",
        f"no_signal_rate={summary['no_signal']['rate']}",
        f"safety_blocked={summary['safety']['blocked']}",
        f"knowledge_coverage_rate={summary['knowledge']['coverage_rate']}",
        f"knowledge_unavailable_rate={summary['knowledge']['unavailable_rate']}",
    ]
    inventory = summary["knowledge"]["inventory"]
    lines.append(f"kb_version={inventory['version'] or 'unavailable'}")
    lines.append(f"kb_approved_cards={inventory['approved_cards']}")
    return "\n".join(lines)


metrics_summary = collect_metrics
aggregate = collect_metrics


def collect_knowledge_inventory(store: KnowledgeStore) -> dict[str, Any]:
    """Return the deploy-visible version and approved-card count, never content."""

    try:
        knowledge = store.load()
    except KnowledgeLookupError:
        return {"version": None, "approved_cards": 0}
    return {"version": knowledge.version, "approved_cards": len(knowledge.cards)}


def log_knowledge_inventory(store: KnowledgeStore | None = None) -> dict[str, Any]:
    """Log startup inventory as IDs, versions, and counts only."""

    import logging

    inventory = collect_knowledge_inventory(store or FileKnowledgeStore())
    logging.getLogger(__name__).info(
        "knowledge inventory version=%s approved_cards=%s",
        inventory["version"],
        inventory["approved_cards"],
    )
    return inventory


def _normalize_bound(value: datetime | None) -> datetime | None:
    """Make a window bound timezone-aware (UTC) to match timestamptz columns."""

    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _event_window(
    *,
    since: datetime | None,
    until: datetime | None,
) -> list[Any]:
    conditions: list[Any] = []
    if since is not None:
        conditions.append(CheckEvent.ts >= since)
    if until is not None:
        conditions.append(CheckEvent.ts < until)
    return conditions


def _consent_window(
    *,
    since: datetime | None,
    until: datetime | None,
) -> list[Any]:
    conditions: list[Any] = []
    if since is not None:
        conditions.append(Consent.ts >= since)
    if until is not None:
        conditions.append(Consent.ts < until)
    return conditions


async def _count_events(session: AsyncSession, conditions: Iterable[Any]) -> int:
    return await _scalar_int(
        session,
        select(func.count()).select_from(CheckEvent).where(*conditions),
    )


async def _breakdown(
    session: AsyncSession,
    column: Any,
    conditions: Iterable[Any],
) -> dict[str, int]:
    rows = (
        await session.execute(
            select(column, func.count())
            .select_from(CheckEvent)
            .where(*conditions)
            .group_by(column)
        )
    ).all()
    return {str(key): int(count) for key, count in rows}


async def _feedback_breakdown(
    session: AsyncSession,
    column: Any,
    *,
    since: datetime | None,
    until: datetime | None,
    exclude_null: bool = False,
) -> dict[str, int]:
    conditions = _feedback_window(since=since, until=until)
    if exclude_null:
        conditions.append(column.is_not(None))
    rows = (
        await session.execute(
            select(column, func.count())
            .select_from(Feedback)
            .join(CheckEvent, Feedback.check_id == CheckEvent.id)
            .where(*conditions)
            .group_by(column)
        )
    ).all()
    return {str(key): int(count) for key, count in rows}


async def _knowledge_metrics(
    session: AsyncSession,
    conditions: Iterable[Any],
) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(CheckEvent.knowledge_card_ids, CheckEvent.retrieval_status)
            .select_from(CheckEvent)
            .where(*conditions, CheckEvent.retrieval_status.is_not(None))
        )
    ).all()
    total = len(rows)
    selected = sum(1 for card_ids, _ in rows if card_ids)
    unavailable = sum(1 for _, status in rows if status == "unavailable")
    return {
        "checks": total,
        "selected": selected,
        "unavailable": unavailable,
        "coverage_rate": _rate(selected, total),
        "unavailable_rate": _rate(unavailable, total),
    }


def _feedback_window(
    *,
    since: datetime | None,
    until: datetime | None,
) -> list[Any]:
    conditions: list[Any] = []
    if since is not None:
        conditions.append(Feedback.ts >= since)
    if until is not None:
        conditions.append(Feedback.ts < until)
    return conditions


async def _decimal_sum(
    session: AsyncSession,
    column: Any,
    conditions: Iterable[Any],
) -> Decimal:
    value = (
        await session.execute(select(func.sum(column)).select_from(CheckEvent).where(*conditions))
    ).scalar_one()
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


async def _scalar_int(session: AsyncSession, statement: Any) -> int:
    value = (await session.execute(statement)).scalar_one()
    return 0 if value is None else int(value)


async def _scalar_float(session: AsyncSession, statement: Any) -> float | None:
    value = (await session.execute(statement)).scalar_one()
    return None if value is None else float(value)


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def _round_money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.000001")))
