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
from app.data.retention import RetentionPolicy, start_retention_scheduler
from app.engine.faces import FACES
from app.engine.url_reputation import install_url_reputation_job
from app.obs.alerts import (
    install_knowledge_availability_alert_job,
    install_operator_alerts,
)
from app.obs.metrics import log_knowledge_inventory
from app.obs.sentry import init_sentry
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
    init_sentry(settings)
    engine = create_database_engine(settings.database_url)
    try:
        await check_database_connection(engine)
        LOGGER.info("Avvalo booted and connected to PostgreSQL")
        log_knowledge_inventory()
        if check_only:
            return

        session_factory = create_session_factory(engine)
        scheduler = start_retention_scheduler(
            session_factory,
            policy=RetentionPolicy(
                story_rejected_days=settings.story_rejected_retention_days
            ),
        )
        install_url_reputation_job(scheduler, session_factory, settings)
        install_knowledge_availability_alert_job(scheduler, session_factory, settings)
        try:
            runners = []
            if settings.web_enabled:
                runners.append(_run_web(settings, session_factory))
                LOGGER.info("Starting web app on %s:%s", settings.web_host, settings.web_port)

            bot_specs = configured_bot_specs(settings)
            if not bot_specs:
                if not runners:
                    LOGGER.warning(
                        "No Telegram bot token is set; idling without a bot. "
                        "Set TELEGRAM_TOKEN."
                    )
                    await asyncio.Event().wait()
                    return
            else:
                for spec in bot_specs:
                    bot = build_bot(spec.token)
                    dispatcher = build_dispatcher(settings, session_factory, FACES[spec.face_id])
                    runners.append(dispatcher.start_polling(bot))
                    LOGGER.info("Starting %s bot (polling)", spec.face_id)
                    if settings.operator_alert_chat_id is not None:
                        install_operator_alerts(
                            bot,
                            settings.operator_alert_chat_id,
                            debounce_s=settings.operator_alert_debounce_s,
                        )

            await asyncio.gather(*runners)
        finally:
            scheduler.shutdown(wait=False)
    finally:
        await engine.dispose()


def configured_bot_specs(settings: Settings) -> list[BotSpec]:
    """Return the configured Telegram bot spec, if the token is usable."""

    token = settings.telegram_token.get_secret_value()
    if not token or token == PLACEHOLDER_TOKEN:
        return []
    return [BotSpec(face_id="family", token=token)]


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
