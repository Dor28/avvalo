"""aiogram bot and dispatcher factories."""

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import router


def build_bot(token: str) -> Bot:
    """Create the aiogram Bot for the given BotFather token."""

    return Bot(token=token)


def build_dispatcher(settings, session_factory, face) -> Dispatcher:
    """Wire shared dependencies into a dispatcher and register the handlers.

    ``settings``, ``session_factory``, and ``face`` are injected into handlers by
    parameter name through aiogram's workflow data.
    """

    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher["settings"] = settings
    dispatcher["session_factory"] = session_factory
    dispatcher["face"] = face
    dispatcher.include_router(router)
    return dispatcher
