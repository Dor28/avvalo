"""Avvalo process entry point."""

import argparse
import asyncio
import logging

from app.config import get_settings
from app.data.db import check_database_connection, create_database_engine

LOGGER = logging.getLogger(__name__)


async def run(*, check_only: bool = False) -> None:
    """Validate configuration, connect to PostgreSQL, and keep the service alive."""

    settings = get_settings()
    engine = create_database_engine(settings.database_url)
    try:
        await check_database_connection(engine)
        LOGGER.info("Avvalo booted and connected to PostgreSQL")
        if not check_only:
            await asyncio.Event().wait()
    finally:
        await engine.dispose()


def main() -> None:
    """Run the service or a one-shot T1 connectivity check."""

    parser = argparse.ArgumentParser(description="Avvalo application")
    parser.add_argument(
        "--check",
        action="store_true",
        help="connect to the database and exit",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(run(check_only=args.check))


if __name__ == "__main__":
    main()
