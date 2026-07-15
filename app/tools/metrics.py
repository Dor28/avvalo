"""Operator CLI for privacy-safe metrics, Scam Pulse, and feedback labels.

    python -m app.tools.metrics                 # all-time, key=value lines
    python -m app.tools.metrics --days 30       # last 30 days
    python -m app.tools.metrics --json          # full JSON summary
    python -m app.tools.metrics pulse --month 2026-07
    python -m app.tools.metrics labels --since 2026-07-01

The output is aggregate-only: no user keys, check IDs, text, links, phone
numbers, or model output ever appear here (see app/obs/metrics.py and
app/obs/pulse.py).
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.data.db import create_database_engine, create_session_factory
from app.obs.metrics import collect_metrics, export_metrics
from app.obs.pulse import collect_labels, collect_pulse, render_labels, render_pulse


async def _run(*, days: int | None, as_json: bool) -> str:
    since = datetime.now(UTC) - timedelta(days=days) if days else None
    settings = get_settings()
    engine = create_database_engine(settings.database_url)
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            if as_json:
                summary = await collect_metrics(session, since=since)
                return json.dumps(summary, indent=2, default=str)
            return await export_metrics(session, since=since)
    finally:
        await engine.dispose()


async def run(
    argv: Sequence[str] | None = None,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    output_dir: Path = Path("out"),
) -> int:
    """Run one CLI command; injectable dependencies keep acceptance tests offline."""

    args = _build_parser().parse_args(argv)
    engine = None
    if session_factory is None:
        settings = get_settings()
        engine = create_database_engine(settings.database_url)
        session_factory = create_session_factory(engine)

    try:
        async with session_factory() as session:
            if args.command == "pulse":
                report = await collect_pulse(session, month=args.month)
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = output_dir / f"pulse_{args.month}.md"
                output_path.write_text(render_pulse(report), encoding="utf-8")
                print(output_path)
                return 0

            if args.command == "labels":
                since = date.fromisoformat(args.since) if args.since else None
                print(render_labels(await collect_labels(session, since=since)), end="")
                return 0

            if args.json:
                since = datetime.now(UTC) - timedelta(days=args.days) if args.days else None
                summary = await collect_metrics(session, since=since)
                print(json.dumps(summary, indent=2, default=str))
            else:
                since = datetime.now(UTC) - timedelta(days=args.days) if args.days else None
                print(await export_metrics(session, since=since))
            return 0
    finally:
        if engine is not None:
            await engine.dispose()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Avvalo privacy-safe metrics export")
    parser.add_argument("--days", type=int, default=None, help="limit to the last N days")
    parser.add_argument("--json", action="store_true", help="print the full JSON summary")
    subparsers = parser.add_subparsers(dest="command")

    pulse_parser = subparsers.add_parser("pulse", help="write one monthly Scam Pulse")
    pulse_parser.add_argument("--month", required=True, help="month in YYYY-MM format")

    labels_parser = subparsers.add_parser("labels", help="print feedback-by-rule labels")
    labels_parser.add_argument("--since", help="earliest feedback date in YYYY-MM-DD format")
    return parser


def main() -> None:
    raise SystemExit(asyncio.run(run()))


if __name__ == "__main__":
    main()
