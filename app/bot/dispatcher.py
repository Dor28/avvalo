"""aiogram bot and dispatcher factories."""

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent, TelegramObject

from app.bot.handlers import router
from app.obs.context import request_context
from app.obs.events import log_error


def build_bot(token: str) -> Bot:
    """Create the aiogram Bot for the given BotFather token."""

    return Bot(token=token)


def build_dispatcher(settings, session_factory) -> Dispatcher:
    """Wire shared dependencies into a dispatcher and register the handlers.

    ``settings`` and ``session_factory`` are injected into handlers by parameter
    name through aiogram's workflow data.
    """

    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher["settings"] = settings
    dispatcher["session_factory"] = session_factory
    dispatcher.update.outer_middleware(_request_context_middleware)
    dispatcher.include_router(router)
    dispatcher.errors.register(_handle_unexpected_error)
    return dispatcher


async def _request_context_middleware(
    handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
    event: TelegramObject,
    data: dict[str, Any],
) -> Any:
    """Give one Telegram update an anonymous ID shared by all of its logs."""

    with request_context() as request_id:
        data["request_id"] = request_id
        return await handler(event, data)


async def _handle_unexpected_error(
    event: ErrorEvent,
    request_id: str | None = None,
) -> bool:
    """Catch-all for exceptions that escape a handler without going through run_check().

    Returning ``True`` marks the update as handled so aiogram's own polling loop
    doesn't also re-raise and log it a second time through its internal logger.
    """

    with request_context(request_id):
        log_error(stage="bot", error_type=event.exception.__class__.__name__)
    return True
