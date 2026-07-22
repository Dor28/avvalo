"""aiogram bot and dispatcher factories."""

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

from app.bot.handlers import router
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
    dispatcher.include_router(router)
    dispatcher.errors.register(_handle_unexpected_error)
    return dispatcher


async def _handle_unexpected_error(event: ErrorEvent) -> bool:
    """Catch-all for exceptions that escape a handler without going through run_check().

    Returning ``True`` marks the update as handled so aiogram's own polling loop
    doesn't also re-raise and log it a second time through its internal logger.
    """

    log_error(stage="bot", error_type=event.exception.__class__.__name__)
    return True
