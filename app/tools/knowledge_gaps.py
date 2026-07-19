"""Read-only, metadata-only knowledge gap report.

    python -m app.tools.knowledge_gaps
    python -m app.tools.knowledge_gaps --days 30 --face family
    python -m app.tools.knowledge_gaps --since 2026-07-01 --until 2026-07-08

The report can show where retrieval missed, but never what a submission said.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings, get_settings
from app.data.db import create_database_engine, create_session_factory
from app.data.models import CheckEvent, Feedback
from app.engine.faces import FACES
from app.engine.knowledge import FileKnowledgeStore, KnowledgeLookupError, KnowledgeStore


async def collect_knowledge_gaps(
    session: AsyncSession,
    *,
    since: datetime,
    until: datetime,
    face: str | None = None,
    knowledge_store: KnowledgeStore | None = None,
) -> dict[str, Any]:
    """Aggregate only allowlisted IDs, enums, counts, and versions."""

    conditions = [CheckEvent.ts >= since, CheckEvent.ts < until]
    if face is not None:
        conditions.append(CheckEvent.face == face)
    rows = (
        await session.execute(
            select(
                CheckEvent.face,
                CheckEvent.language,
                CheckEvent.rule_ids,
                CheckEvent.knowledge_card_ids,
                CheckEvent.retrieval_status,
                CheckEvent.retrieval_mode,
                CheckEvent.router_status,
                Feedback.usefulness,
            )
            .select_from(CheckEvent)
            .outerjoin(Feedback, Feedback.check_id == CheckEvent.id)
            .where(*conditions)
        )
    ).all()

    coverage: dict[tuple[str, str], Counter[str]] = {}
    gaps: Counter[tuple[str, str, tuple[str, ...]]] = Counter()
    card_usage: Counter[str] = Counter()
    router_health: Counter[str] = Counter()
    for (
        event_face,
        language,
        rule_ids,
        card_ids,
        retrieval_status,
        retrieval_mode,
        router_status,
        usefulness,
    ) in rows:
        if retrieval_status is None:
            continue
        key = (event_face, language)
        bucket = coverage.setdefault(key, Counter())
        bucket["checks"] += 1
        if card_ids:
            bucket["found"] += 1
        elif retrieval_status == "unavailable":
            bucket["unavailable"] += 1
        else:
            bucket["no_match"] += 1
        card_usage.update(card_ids or [])
        if retrieval_status == "empty" and usefulness == "no":
            gaps[(event_face, language, tuple(sorted(rule_ids or [])))] += 1
        if retrieval_mode:
            router_health[f"mode:{retrieval_mode}"] += 1
        if router_status and router_status != "not_used":
            router_health[f"status:{router_status}"] += 1

    approved_ids = _approved_ids(knowledge_store or FileKnowledgeStore(), face=face)
    coverage_rows = [
        {
            "face": item_face,
            "language": language,
            "checks": counts["checks"],
            "found": counts["found"],
            "coverage_rate": _rate(counts["found"], counts["checks"]),
            "no_match": counts["no_match"],
            "unavailable": counts["unavailable"],
        }
        for (item_face, language), counts in sorted(coverage.items())
    ]
    gap_rows = [
        {
            "face": item_face,
            "language": language,
            "rule_ids": list(rule_ids),
            "count": count,
        }
        for (item_face, language, rule_ids), count in sorted(
            gaps.items(), key=lambda item: (-item[1], item[0])
        )
    ]
    usage_rows = [
        {"card_id": card_id, "count": card_usage[card_id]}
        for card_id in sorted(set(card_usage) | approved_ids)
    ]
    return {
        "window": {"since": since.isoformat(), "until": until.isoformat()},
        "coverage": coverage_rows,
        "gaps": gap_rows,
        "card_usage": usage_rows,
        "unused_cards": sorted(approved_ids - set(card_usage)),
        "router_health": dict(sorted(router_health.items())),
    }


def render_knowledge_gaps(report: dict[str, Any]) -> str:
    """Render a decision-oriented operator report rather than a raw dump."""

    lines = [
        "Avvalo knowledge-gap report",
        f"Window: {report['window']['since']} to {report['window']['until']}",
        "",
        "Coverage by face and language:",
    ]
    if report["coverage"]:
        for row in report["coverage"]:
            lines.append(
                f"- {row['face']}/{row['language']}: {row['found']}/{row['checks']} "
                f"found ({row['coverage_rate']:.1%}); no match={row['no_match']}"
            )
            lines.append(f"  unavailable={row['unavailable']} (outage, not a no-match)")
    else:
        lines.append("- No checks in this window.")

    lines.extend(["", "Negative-feedback gaps (most frequent first):"])
    if report["gaps"]:
        for row in report["gaps"]:
            rules = ",".join(row["rule_ids"]) or "(no rules)"
            lines.append(
                f"- {row['count']} x {row['face']}/{row['language']} rules={rules}"
            )
    else:
        lines.append("- None.")

    lines.extend(["", "Card usage:"])
    if report["card_usage"]:
        for row in report["card_usage"]:
            lines.append(f"- {row['card_id']}: {row['count']}")
    else:
        lines.append("- No approved cards or selections.")
    unused = ", ".join(report["unused_cards"]) or "none"
    lines.append(f"Unused approved cards: {unused}")

    if report["router_health"]:
        lines.extend(["", "Router health:"])
        lines.extend(
            f"- {key}: {value}" for key, value in report["router_health"].items()
        )

    lines.extend(
        [
            "",
            "Privacy note: submitted content is not stored. This report shows where "
            "the system missed, not what the message said. Identify the pattern through "
            "the explicitly consented, minimized story corpus before writing a card.",
        ]
    )
    return "\n".join(lines) + "\n"


async def run(
    argv: Sequence[str] | None = None,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    settings: Settings | None = None,
) -> int:
    """Run the read-only CLI with injectable database dependencies."""

    args = _parser().parse_args(argv)
    settings = settings or get_settings()
    until = _date_bound(args.until, end=True) if args.until else datetime.now(UTC)
    if args.since:
        since = _date_bound(args.since, end=False)
    else:
        days = args.days or settings.knowledge_gap_default_days
        since = until - timedelta(days=days)

    engine = None
    if session_factory is None:
        engine = create_database_engine(settings.database_url)
        session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session:
            report = await collect_knowledge_gaps(
                session,
                since=since,
                until=until,
                face=args.face,
            )
            print(render_knowledge_gaps(report), end="")
        return 0
    finally:
        if engine is not None:
            await engine.dispose()


def _approved_ids(store: KnowledgeStore, *, face: str | None) -> set[str]:
    ids: set[str] = set()
    for face_id in ([face] if face else sorted(FACES)):
        try:
            ids.update(card.id for card in store.load(face_id).cards)
        except KnowledgeLookupError:
            continue
    return ids


def _rate(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def _date_bound(value: str, *, end: bool) -> datetime:
    parsed = date.fromisoformat(value)
    if end:
        parsed += timedelta(days=1)
    return datetime.combine(parsed, time.min, tzinfo=UTC)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Privacy-safe knowledge gap report")
    parser.add_argument("--days", type=int, help="look back N days (default from settings)")
    parser.add_argument("--since", help="inclusive start date in YYYY-MM-DD")
    parser.add_argument("--until", help="inclusive end date in YYYY-MM-DD")
    parser.add_argument("--face", choices=sorted(FACES))
    return parser


def main() -> None:
    raise SystemExit(asyncio.run(run()))


if __name__ == "__main__":
    main()
