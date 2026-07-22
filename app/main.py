"""Avvalo process entry point."""

import argparse
import asyncio
import logging
from collections.abc import Awaitable

import uvicorn

from app.bot.dispatcher import build_bot, build_dispatcher
from app.config import Settings, get_settings
from app.data.db import (
    check_database_connection,
    create_database_engine,
    create_session_factory,
)
from app.data.retention import RetentionPolicy, start_retention_scheduler
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

            token = configured_bot_token(settings)
            if token is None:
                if not runners:
                    LOGGER.warning(
                        "No Telegram bot token is set; idling without a bot. "
                        "Set TELEGRAM_TOKEN."
                    )
                    await asyncio.Event().wait()
                    return
            else:
                bot = build_bot(token)
                dispatcher = build_dispatcher(settings, session_factory)
                # Uvicorn owns SIGINT/SIGTERM when the web channel is active.
                # Otherwise aiogram remains the signal owner for bot-only runs.
                runners.append(
                    dispatcher.start_polling(
                        bot,
                        handle_signals=not settings.web_enabled,
                    )
                )
                LOGGER.info("Starting Telegram bot (polling)")
                if settings.operator_alert_chat_id is not None:
                    install_operator_alerts(
                        bot,
                        settings.operator_alert_chat_id,
                        debounce_s=settings.operator_alert_debounce_s,
                    )

            await _run_service_runners(runners)
        finally:
            scheduler.shutdown(wait=False)
    finally:
        await engine.dispose()


def configured_bot_token(settings: Settings) -> str | None:
    """Return the Telegram bot token when one is usably configured."""

    token = settings.telegram_token.get_secret_value()
    if not token or token == PLACEHOLDER_TOKEN:
        return None
    return token


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


async def _run_service_runners(runners: list[Awaitable[None]]) -> None:
    """Run services together and stop peers when any runner exits.

    In the combined web + bot process Uvicorn is the sole OS-signal owner. Once
    its runner returns after SIGINT/SIGTERM, cancelling the polling runner lets
    aiogram execute its own shutdown hooks and close the bot session.
    """

    tasks = [asyncio.ensure_future(runner) for runner in runners]
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            task.result()
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def main() -> None:
    """Run the service or a one-shot T1 connectivity check."""

    parser = argparse.ArgumentParser(description="Avvalo application")
    parser.add_argument("--check", action="store_true", help="connect to the database and exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(run(check_only=args.check))


if __name__ == "__main__":
    main()
