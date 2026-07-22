"""Catch-all error handling: aiogram's global error handler and the debounced
Telegram alert to the operator, both driven by log_error()."""

import asyncio
import logging

from aiogram.types import ErrorEvent, Update

from app.bot.dispatcher import _handle_unexpected_error, build_dispatcher
from app.obs.alerts import OperatorAlertHandler
from app.obs.events import log_error


class _FakeBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


async def test_bot_error_handler_logs_and_marks_handled(caplog) -> None:
    caplog.set_level(logging.ERROR, logger="app.obs.events")
    event = ErrorEvent(update=Update(update_id=1), exception=ValueError("boom"))

    result = await _handle_unexpected_error(event)

    assert result is True
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "event=app_error" in messages
    assert "'stage': 'bot'" in messages
    assert "'error_type': 'ValueError'" in messages
    assert "boom" not in messages


def test_build_dispatcher_registers_an_error_handler() -> None:
    dispatcher = build_dispatcher(None, None)
    assert len(dispatcher.errors.handlers) >= 1


async def test_operator_alert_handler_sends_and_debounces() -> None:
    bot = _FakeBot()
    handler = OperatorAlertHandler(bot, chat_id=42, debounce_s=900.0)
    logger = logging.getLogger("app.obs.events")
    logger.addHandler(handler)
    try:
        log_error("llm", "LLMProviderError")
        log_error("llm", "LLMProviderError")  # same key -- debounced
        log_error("ocr", "OCRProviderError")  # different stage/type -- sent

        await asyncio.gather(*handler._pending)  # let the fire-and-forget sends finish
    finally:
        logger.removeHandler(handler)

    assert len(bot.sent) == 2
    assert {chat_id for chat_id, _ in bot.sent} == {42}
    texts = [text for _, text in bot.sent]
    assert any("stage=llm" in t and "type=LLMProviderError" in t for t in texts)
    assert any("stage=ocr" in t and "type=OCRProviderError" in t for t in texts)


async def test_operator_alert_includes_http_status_when_present() -> None:
    bot = _FakeBot()
    handler = OperatorAlertHandler(bot, chat_id=42, debounce_s=900.0)
    logger = logging.getLogger("app.obs.events")
    logger.addHandler(handler)
    try:
        log_error("llm", "RateLimitError", status_code=429)
        await asyncio.gather(*handler._pending)
    finally:
        logger.removeHandler(handler)

    assert len(bot.sent) == 1
    assert "type=RateLimitError" in bot.sent[0][1]
    assert "status=429" in bot.sent[0][1]


async def test_operator_alert_sends_first_alert_shortly_after_boot(monkeypatch) -> None:
    """Regression: time.monotonic() counts from boot, so a freshly restarted host
    reports a small value. The first alert of a key must still go out -- a 0.0
    "never sent" sentinel would debounce it away for the whole window."""

    bot = _FakeBot()
    handler = OperatorAlertHandler(bot, chat_id=42, debounce_s=900.0)
    monkeypatch.setattr("app.obs.alerts.time.monotonic", lambda: 5.0)  # 5s of uptime
    logger = logging.getLogger("app.obs.events")
    logger.addHandler(handler)
    try:
        log_error("llm", "LLMProviderError")
        await asyncio.gather(*handler._pending)
    finally:
        logger.removeHandler(handler)

    assert len(bot.sent) == 1


async def test_operator_alert_handler_skips_safety_fallback() -> None:
    bot = _FakeBot()
    handler = OperatorAlertHandler(bot, chat_id=42, debounce_s=900.0)
    logger = logging.getLogger("app.obs.events")
    logger.addHandler(handler)
    try:
        log_error(
            "validate", "SafetyValidationError", reason="verify block is empty"
        )
        await asyncio.sleep(0)
    finally:
        logger.removeHandler(handler)

    assert bot.sent == []
