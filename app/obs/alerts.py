"""Debounced Telegram alerts to the operator, driven by log_error() records.

Attaches as a standard logging.Handler on the "app.obs.events" logger, so it
only ever sees the same allowlisted, content-scrubbed fields already destined
for the local error log — nothing new is read from the exception, the request,
or the update.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.data.models import CheckEvent
from app.obs.events import log_error

_ALERT_STAGES = {"ocr", "llm", "web", "bot", "knowledge", "url_reputation"}


class OperatorAlertHandler(logging.Handler):
    """Forward log_error() records to the operator's Telegram chat, debounced.

    ``validate`` (safety_fallback) is intentionally excluded: it's an expected,
    routine outcome of the safety validator, not a system fault worth paging.
    """

    def __init__(self, bot: Bot, chat_id: int, *, debounce_s: float = 900.0) -> None:
        super().__init__(level=logging.ERROR)
        self._bot = bot
        self._chat_id = chat_id
        self._debounce_s = debounce_s
        self._last_sent: dict[str, float] = {}
        self._pending: set[asyncio.Task] = set()

    def emit(self, record: logging.LogRecord) -> None:
        fields = getattr(record, "avvalo_error", None)
        if not fields:
            return
        stage = fields.get("stage")
        error_type = fields.get("error_type")
        if stage not in _ALERT_STAGES or not error_type:
            return

        key = f"{stage}:{error_type}"
        now = time.monotonic()
        # `None` (never sent) rather than 0.0: time.monotonic() counts from boot, so a
        # 0.0 sentinel silently debounces the *first* alert of every key for the first
        # `debounce_s` seconds of uptime -- i.e. right after each deploy or restart.
        last_sent = self._last_sent.get(key)
        if last_sent is not None and now - last_sent < self._debounce_s:
            return
        self._last_sent[key] = now

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # No running event loop (e.g. during shutdown) -- drop the alert.

        status_code = fields.get("status_code")
        request_id = fields.get("request_id")
        suffix = f" status={status_code}" if status_code is not None else ""
        if request_id is not None:
            suffix += f" request_id={request_id}"
        text = f"Avvalo error: stage={stage} type={error_type}{suffix}"
        task = loop.create_task(self._bot.send_message(self._chat_id, text))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)


def install_operator_alerts(bot: Bot, chat_id: int, *, debounce_s: float = 900.0) -> None:
    """Attach the debounced Telegram alert handler to the error-log stream."""

    logging.getLogger("app.obs.events").addHandler(
        OperatorAlertHandler(bot, chat_id, debounce_s=debounce_s)
    )


@dataclass(frozen=True)
class KnowledgeAvailability:
    """Aggregate retrieval availability over one sustained window."""

    checks: int
    unavailable: int
    rate: float
    alert: bool


async def evaluate_knowledge_availability(
    session: AsyncSession,
    *,
    since: datetime,
    threshold: float,
) -> KnowledgeAvailability:
    """Evaluate a metadata-only unavailable-rate threshold."""

    total = int(
        (
            await session.execute(
                select(func.count())
                .select_from(CheckEvent)
                .where(
                    CheckEvent.ts >= since,
                    CheckEvent.retrieval_status.is_not(None),
                )
            )
        ).scalar_one()
    )
    unavailable = int(
        (
            await session.execute(
                select(func.count())
                .select_from(CheckEvent)
                .where(
                    CheckEvent.ts >= since,
                    CheckEvent.retrieval_status == "unavailable",
                )
            )
        ).scalar_one()
    )
    rate = 0.0 if total == 0 else unavailable / total
    return KnowledgeAvailability(
        checks=total,
        unavailable=unavailable,
        rate=rate,
        alert=unavailable > 0 and rate >= threshold,
    )


async def run_knowledge_availability_alert_job(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> KnowledgeAvailability:
    """Evaluate and emit through the existing privacy-safe alert stream."""

    window = settings.knowledge_unavailable_alert_window_minutes
    since = datetime.now(UTC) - timedelta(minutes=window)
    async with session_factory() as session:
        availability = await evaluate_knowledge_availability(
            session,
            since=since,
            threshold=settings.knowledge_unavailable_alert_threshold,
        )
    if availability.alert:
        log_error(
            "knowledge",
            "KnowledgeUnavailableSpike",
            rate=round(availability.rate, 4),
            checks=availability.checks,
            window_minutes=window,
        )
    return availability


def install_knowledge_availability_alert_job(
    scheduler: AsyncIOScheduler,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    """Install the sustained knowledge outage check on the shared scheduler."""

    scheduler.add_job(
        run_knowledge_availability_alert_job,
        "interval",
        args=[session_factory, settings],
        minutes=settings.knowledge_unavailable_alert_window_minutes,
        id="knowledge_availability_alert",
        replace_existing=True,
    )
