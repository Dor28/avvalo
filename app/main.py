"""Avvalo process entry point."""

import argparse
import asyncio
import logging

from app.bot.dispatcher import build_bot, build_dispatcher
from app.config import get_settings
from app.data.db import (
    check_database_connection,
    create_database_engine,
    create_session_factory,
)
from app.engine.faces import FACES

LOGGER = logging.getLogger(__name__)

PLACEHOLDER_TOKEN = "development-placeholder"


async def run(*, check_only: bool = False) -> None:
    """Validate config, connect to PostgreSQL, then run the bot (or just check)."""

    settings = get_settings()
    engine = create_database_engine(settings.database_url)
    try:
        await check_database_connection(engine)
        LOGGER.info("Avvalo booted and connected to PostgreSQL")
        if check_only:
            return

        token = settings.telegram_token_family_shield.get_secret_value()
        if not token or token == PLACEHOLDER_TOKEN:
            LOGGER.warning(
                "TELEGRAM_TOKEN_FAMILY_SHIELD is not set; idling without a bot. "
                "Set a BotFather token to run the Family Shield bot."
            )
            await asyncio.Event().wait()
            return

        session_factory = create_session_factory(engine)
        bot = build_bot(token)
        dispatcher = build_dispatcher(settings, session_factory, FACES["family_shield"])
        LOGGER.info("Starting Family Shield bot (polling)")
        await dispatcher.start_polling(bot)
    finally:
        await engine.dispose()


def main() -> None:
    """Run the service or a one-shot T1 connectivity check."""

    parser = argparse.ArgumentParser(description="Avvalo application")
    parser.add_argument("--check", action="store_true", help="connect to the database and exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(run(check_only=args.check))


if __name__ == "__main__":
    main()
