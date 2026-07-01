"""Avvalo process entry point."""

import argparse
import asyncio
import logging
from dataclasses import dataclass

import uvicorn

from app.bot.dispatcher import build_bot, build_dispatcher
from app.config import Settings, get_settings
from app.data.db import (
    check_database_connection,
    create_database_engine,
    create_session_factory,
)
from app.data.retention import start_retention_scheduler
from app.engine.faces import FACES
from app.web.app import create_app

LOGGER = logging.getLogger(__name__)

PLACEHOLDER_TOKEN = "development-placeholder"


@dataclass(frozen=True)
class BotSpec:
    face_id: str
    token: str


async def run(*, check_only: bool = False) -> None:
    """Validate config, connect to PostgreSQL, then run the bot (or just check)."""

    settings = get_settings()
    engine = create_database_engine(settings.database_url)
    try:
        await check_database_connection(engine)
        LOGGER.info("Avvalo booted and connected to PostgreSQL")
        if check_only:
            return

        session_factory = create_session_factory(engine)
        scheduler = start_retention_scheduler(session_factory)
        try:
            runners = []
            if settings.web_enabled:
                runners.append(_run_web(settings, session_factory))
                LOGGER.info("Starting web app on %s:%s", settings.web_host, settings.web_port)

            bot_specs = configured_bot_specs(settings)
            if not bot_specs:
                if not runners:
                    LOGGER.warning(
                        "No Telegram bot tokens are set; idling without a bot. "
                        "Set TELEGRAM_TOKEN_FAMILY_SHIELD and/or TELEGRAM_TOKEN_SELLER_GUARD."
                    )
                    await asyncio.Event().wait()
                    return
            else:
                for spec in bot_specs:
                    bot = build_bot(spec.token)
                    dispatcher = build_dispatcher(settings, session_factory, FACES[spec.face_id])
                    runners.append(dispatcher.start_polling(bot))
                    LOGGER.info("Starting %s bot (polling)", spec.face_id)

            await asyncio.gather(*runners)
        finally:
            scheduler.shutdown(wait=False)
    finally:
        await engine.dispose()


def configured_bot_specs(settings: Settings) -> list[BotSpec]:
    """Return one bot spec for each configured face token."""

    specs = [
        BotSpec(
            face_id="family_shield",
            token=settings.telegram_token_family_shield.get_secret_value(),
        )
    ]
    if settings.telegram_token_seller_guard is not None:
        specs.append(
            BotSpec(
                face_id="seller_guard",
                token=settings.telegram_token_seller_guard.get_secret_value(),
            )
        )
    return [spec for spec in specs if spec.token and spec.token != PLACEHOLDER_TOKEN]


async def _run_web(settings: Settings, session_factory) -> None:
    """Serve the FastAPI web channel in the shared process."""

    config = uvicorn.Config(
        create_app(settings=settings, session_factory=session_factory),
        host=settings.web_host,
        port=settings.web_port,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    """Run the service or a one-shot T1 connectivity check."""

    parser = argparse.ArgumentParser(description="Avvalo application")
    parser.add_argument("--check", action="store_true", help="connect to the database and exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(run(check_only=args.check))


if __name__ == "__main__":
    main()
