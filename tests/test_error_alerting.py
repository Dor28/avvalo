"""Catch-all error handling: aiogram's global error handler and the debounced
Telegram alert to the operator, both driven by log_error()."""

import asyncio
import logging

import pytest
from aiogram.types import ErrorEvent, Update

from app.bot.dispatcher import (
    _handle_unexpected_error,
    _request_context_middleware,
    build_dispatcher,
)
from app.obs.alerts import OperatorAlertHandler
from app.obs.context import REQUEST_ID_RE, current_request_id, request_context
from app.obs.events import log_error, log_event


class _FakeBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


async def test_bot_error_handler_logs_and_marks_handled(caplog) -> None:
    caplog.set_level(logging.ERROR, logger="app.obs.events")
    event = ErrorEvent(update=Update(update_id=1), exception=ValueError("boom"))
    request_id = "a" * 32

    result = await _handle_unexpected_error(event, request_id=request_id)

    assert result is True
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "event=app_error" in messages
    assert "'stage': 'bot'" in messages
    assert "'error_type': 'ValueError'" in messages
    assert f"'request_id': '{request_id}'" in messages
    assert "boom" not in messages


async def test_bot_middleware_correlates_update_logs_and_clears_context(caplog) -> None:
    caplog.set_level(logging.INFO, logger="app.obs.events")
    data = {}

    async def handler(_event, middleware_data):
        assert current_request_id() == middleware_data["request_id"]
        log_event("consent_shown", language="ru")
        return True

    result = await _request_context_middleware(handler, Update(update_id=2), data)

    assert result is True
    assert REQUEST_ID_RE.fullmatch(data["request_id"])
    assert current_request_id() is None
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert f"'request_id': '{data['request_id']}'" in messages


async def test_bot_error_reuses_the_update_request_id(caplog) -> None:
    caplog.set_level(logging.INFO, logger="app.obs.events")
    data = {}
    update = Update(update_id=3)

    async def failing_handler(_event, _middleware_data):
        log_event("check_started", language="ru", input_type="text")
        raise ValueError("submitted text must never reach the error log")

    with pytest.raises(ValueError):
        await _request_context_middleware(failing_handler, update, data)

    await _handle_unexpected_error(
        ErrorEvent(update=update, exception=ValueError("private failure detail")),
        request_id=data["request_id"],
    )

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert messages.count(data["request_id"]) == 2
    assert "submitted text" not in messages
    assert "private failure detail" not in messages


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
        with request_context("b" * 32):
            log_error("llm", "RateLimitError", status_code=429)
        await asyncio.gather(*handler._pending)
    finally:
        logger.removeHandler(handler)

    assert len(bot.sent) == 1
    assert "type=RateLimitError" in bot.sent[0][1]
    assert "status=429" in bot.sent[0][1]
    assert "request_id=" + "b" * 32 in bot.sent[0][1]


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
