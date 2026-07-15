"""Debounced Telegram alerts to the operator, driven by log_error() records.

Attaches as a standard logging.Handler on the "app.obs.events" logger, so it
only ever sees the same allowlisted, content-scrubbed fields already destined
for the local error log and Sentry — nothing new is read from the exception,
the request, or the update.
"""

from __future__ import annotations

import asyncio
import logging
import time

from aiogram import Bot

_ALERT_STAGES = {"ocr", "llm", "web", "bot"}


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
        if now - self._last_sent.get(key, 0.0) < self._debounce_s:
            return
        self._last_sent[key] = now

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # No running event loop (e.g. during shutdown) -- drop the alert.

        status_code = fields.get("status_code")
        suffix = f" status={status_code}" if status_code is not None else ""
        text = f"Avvalo error: stage={stage} type={error_type}{suffix}"
        task = loop.create_task(self._bot.send_message(self._chat_id, text))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)


def install_operator_alerts(bot: Bot, chat_id: int, *, debounce_s: float = 900.0) -> None:
    """Attach the debounced Telegram alert handler to the error-log stream."""

    logging.getLogger("app.obs.events").addHandler(
        OperatorAlertHandler(bot, chat_id, debounce_s=debounce_s)
    )
