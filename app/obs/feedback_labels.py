"""Privacy-safe feedback-label aggregations for internal product review.

Only categorical fields already stored in ``check_event`` and ``feedback`` are
read. User keys, check IDs, and submitted content are never selected or returned.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.models import CheckEvent, Feedback
from app.engine.rules import load_rule_pack

_USEFUL_VALUES = {"yes", "partly"}
_CANDIDATE_MIN_SAMPLES = 5
_CANDIDATE_GAP = 0.15


def rule_family_map() -> dict[str, str]:
    """Return the current rule-id to scam-family mapping from the active pack."""

    return {rule.id: rule.family for rule in load_rule_pack().rules}


async def collect_labels(
    session: AsyncSession,
    *,
    since: date | datetime | None = None,
) -> dict[str, Any]:
    """Correlate feedback with rule IDs and the overall baseline."""

    since_bound = _since_bound(since)
    statement = (
        select(CheckEvent.rule_ids, Feedback.usefulness, Feedback.next_action)
        .join(Feedback, Feedback.check_id == CheckEvent.id)
        .order_by(Feedback.ts)
    )
    if since_bound is not None:
        statement = statement.where(Feedback.ts >= since_bound)
    rows = (await session.execute(statement)).all()

    total = len(rows)
    total_useful = sum(1 for _, usefulness, _ in rows if usefulness in _USEFUL_VALUES)
    overall_useful_rate = _rate(total_useful, total)
    overall_actions = Counter(action for _, _, action in rows if action is not None)

    responses: Counter[str] = Counter()
    useful: Counter[str] = Counter()
    actions: dict[str, Counter[str]] = defaultdict(Counter)
    family_by_rule = rule_family_map()

    for rule_ids, usefulness, next_action in rows:
        for rule_id in dict.fromkeys(rule_ids or []):
            responses[rule_id] += 1
            if usefulness in _USEFUL_VALUES:
                useful[rule_id] += 1
            if next_action is not None:
                actions[rule_id][next_action] += 1

    rules: list[dict[str, Any]] = []
    for rule_id in sorted(responses):
        rule_rate = _rate(useful[rule_id], responses[rule_id])
        gap = round(overall_useful_rate - rule_rate, 4)
        rules.append(
            {
                "rule_id": rule_id,
                "family": family_by_rule.get(rule_id, "unmapped"),
                "responses": responses[rule_id],
                "useful": useful[rule_id],
                "useful_rate": rule_rate,
                "gap_from_baseline": gap,
                "candidate": responses[rule_id] >= _CANDIDATE_MIN_SAMPLES
                and gap >= _CANDIDATE_GAP,
                "next_actions": dict(sorted(actions[rule_id].items())),
            }
        )

    return {
        "since": since_bound.date().isoformat() if since_bound is not None else None,
        "labeled_checks": total,
        "useful_checks": total_useful,
        "overall_useful_rate": overall_useful_rate,
        "overall_next_actions": dict(sorted(overall_actions.items())),
        "rules": rules,
    }


def render_labels(report: dict[str, Any]) -> str:
    """Render feedback correlations without identifiers or content."""

    since = report["since"] or "all time"
    lines = [
        "# Avvalo Feedback Labels",
        "",
        f"- Since: {since}",
        f"- Labeled checks: {report['labeled_checks']}",
        f"- Useful or partly useful: {report['useful_checks']}",
        f"- Overall useful rate: {report['overall_useful_rate']:.1%}",
        "",
        "| Rule ID | Family | Responses | Useful | Useful rate | Gap vs baseline | Candidate |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    if report["rules"]:
        for row in report["rules"]:
            lines.append(
                f"| {row['rule_id']} | {row['family']} | {row['responses']} | "
                f"{row['useful']} | {row['useful_rate']:.1%} | "
                f"{row['gap_from_baseline']:+.1%} | "
                f"{'review' if row['candidate'] else '—'} |"
            )
    else:
        lines.append("| No labeled rule hits | — | 0 | 0 | 0.0% | +0.0% | — |")

    lines.extend(
        [
            "",
            "## Next-action distribution vs overall baseline",
            "",
            "| Rule ID | Action | Count | Rule rate | Overall count | Overall rate | Delta |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    action_total = sum(report["overall_next_actions"].values())
    action_rows = 0
    for row in report["rules"]:
        rule_action_total = sum(row["next_actions"].values())
        for action in sorted(set(row["next_actions"]) | set(report["overall_next_actions"])):
            count = row["next_actions"].get(action, 0)
            overall_count = report["overall_next_actions"].get(action, 0)
            rule_rate = _rate(count, rule_action_total)
            overall_rate = _rate(overall_count, action_total)
            lines.append(
                f"| {row['rule_id']} | {action} | {count} | {rule_rate:.1%} | "
                f"{overall_count} | {overall_rate:.1%} | {rule_rate - overall_rate:+.1%} |"
            )
            action_rows += 1
    if action_rows == 0:
        lines.append("| No next-action labels | — | 0 | 0.0% | 0 | 0.0% | +0.0% |")
    return "\n".join(lines) + "\n"


def _since_bound(value: date | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    return datetime(value.year, value.month, value.day, tzinfo=UTC)


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)
