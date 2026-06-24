"""Telegram handlers: onboarding, consent, privacy, and deletion (§12).

No handler stores or echoes submitted content. The consent gate ensures content
is only accepted after the current privacy notice has been agreed to.
"""

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import consent_keyboard, language_keyboard
from app.bot.states import Onboarding
from app.bot.texts import DEFAULT_LANGUAGE, LANGUAGES, t
from app.config import Settings
from app.data import repo
from app.privacy.consent import grant_consent, is_consent_current
from app.privacy.user_key import derive_user_key

LOGGER = logging.getLogger(__name__)
router = Router()


def _user_key(user_id: int, settings: Settings) -> str:
    return derive_user_key(user_id, secret=settings.app_hmac_secret.get_secret_value())


async def _language(state: FSMContext) -> str:
    data = await state.get_data()
    return data.get("language", DEFAULT_LANGUAGE)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, settings, session_factory, face) -> None:
    user_key = _user_key(message.from_user.id, settings)
    async with session_factory() as session:
        consent = await repo.get_consent(session, user_key=user_key, face=face.id)

    if is_consent_current(consent, settings.notice_version):
        await state.set_state(Onboarding.ready)
        await state.update_data(language=consent.language)
        await message.answer(t("ready", consent.language))
        return

    await state.set_state(Onboarding.choosing_language)
    await message.answer(
        t("choose_language", DEFAULT_LANGUAGE),
        reply_markup=language_keyboard(),
    )


@router.message(Command("privacy"))
async def cmd_privacy(message: Message, state: FSMContext) -> None:
    await message.answer(t("privacy", await _language(state)))


@router.message(Command("delete_my_data"))
async def cmd_delete_my_data(
    message: Message, state: FSMContext, settings, session_factory
) -> None:
    user_key = _user_key(message.from_user.id, settings)
    async with session_factory() as session:
        await repo.delete_user_data(session, user_key=user_key)
        await session.commit()

    language = await _language(state)
    await state.clear()
    await message.answer(t("data_deleted", language))
    LOGGER.info("deletion_completed")


@router.callback_query(F.data.startswith("lang:"))
async def on_language_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    language = callback.data.split(":", 1)[1]
    if language not in LANGUAGES:
        await callback.answer()
        return

    await state.update_data(language=language)
    await state.set_state(Onboarding.awaiting_consent)
    await callback.message.edit_text(
        t("privacy_notice", language),
        reply_markup=consent_keyboard(language),
    )
    await callback.answer()


@router.callback_query(F.data == "consent:accept")
async def on_consent_accepted(
    callback: CallbackQuery, state: FSMContext, settings, session_factory, face
) -> None:
    language = (await state.get_data()).get("language", DEFAULT_LANGUAGE)
    user_key = _user_key(callback.from_user.id, settings)
    async with session_factory() as session:
        await grant_consent(
            session,
            user_key=user_key,
            face=face.id,
            language=language,
            notice_version=settings.notice_version,
        )
        await session.commit()

    await state.set_state(Onboarding.ready)
    await callback.message.edit_text(t("ready", language))
    await callback.answer()
    LOGGER.info("consent_accepted face=%s language=%s", face.id, language)


@router.message(Onboarding.ready)
async def on_ready_input(message: Message, state: FSMContext) -> None:
    # The analysis engine is wired in later tasks. Never store or echo content.
    await message.answer(t("analysis_pending", await _language(state)))


@router.message()
async def on_unconsented(message: Message, state: FSMContext) -> None:
    await message.answer(t("need_consent", await _language(state)))
