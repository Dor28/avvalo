"""Operator CLI: print the privacy-safe metrics aggregate for the pitch/demo.

    python -m app.tools.metrics                 # all-time, key=value lines
    python -m app.tools.metrics --days 30       # last 30 days
    python -m app.tools.metrics --json          # full JSON summary

The output is aggregate-only: no user keys, check IDs, text, links, phone
numbers, or model output ever appear here (see app/obs/metrics.py).
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime, timedelta

from app.config import get_settings
from app.data.db import create_database_engine, create_session_factory
from app.obs.metrics import collect_metrics, export_metrics


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Avvalo privacy-safe metrics export")
    parser.add_argument("--days", type=int, default=None, help="limit to the last N days")
    parser.add_argument("--json", action="store_true", help="print the full JSON summary")
    args = parser.parse_args()
    print(asyncio.run(_run(days=args.days, as_json=args.json)))


if __name__ == "__main__":
    main()
