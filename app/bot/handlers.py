"""Telegram handlers: onboarding, consent, privacy, and deletion (§12).

No handler stores or echoes submitted content. The consent gate ensures content
is only accepted after the current privacy notice has been agreed to.
"""

import hmac
from io import BytesIO
from uuid import UUID

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.keyboards import (
    consent_callback_data,
    consent_keyboard,
    language_keyboard,
    parse_consent_callback,
    parse_feedback_callback,
    post_check_keyboard,
    telegram_share_url,
)
from app.bot.states import Onboarding
from app.bot.texts import DEFAULT_LANGUAGE, LANGUAGES, entry_text, t
from app.config import Settings
from app.data import repo
from app.engine import CheckInput, CheckStatus, InputType, Language, run_check
from app.engine.faces import Face
from app.engine.format import share_summary
from app.obs.events import log_event
from app.privacy.consent import grant_consent, is_consent_current
from app.privacy.user_key import derive_user_key

_FEEDBACK_STATUSES = {CheckStatus.ok, CheckStatus.no_signal}

router = Router()


def _user_key(user_id: int, settings: Settings) -> str:
    return derive_user_key(user_id, secret=settings.app_hmac_secret.get_secret_value())


async def _language(state: FSMContext) -> str:
    data = await state.get_data()
    return data.get("language", DEFAULT_LANGUAGE)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, settings, session_factory, face) -> None:
    user = message.from_user
    if user is None:
        return
    user_key = _user_key(user.id, settings)
    async with session_factory() as session:
        consent = await repo.get_consent(session, user_key=user_key, face=face.id)

    if is_consent_current(consent, settings.notice_version):
        await state.set_state(Onboarding.ready)
        await state.update_data(language=consent.language)
        await message.answer(entry_text(face.id, consent.language))
        return

    await state.set_state(Onboarding.choosing_language)
    await message.answer(
        f'{t("start_intro", DEFAULT_LANGUAGE)}\n\n{t("choose_language", DEFAULT_LANGUAGE)}',
        reply_markup=language_keyboard(),
    )


@router.message(Command("privacy"))
async def cmd_privacy(message: Message, state: FSMContext) -> None:
    await message.answer(t("privacy", await _language(state)))


@router.message(Command("delete_my_data"))
async def cmd_delete_my_data(
    message: Message, state: FSMContext, settings, session_factory, face
) -> None:
    user = message.from_user
    if user is None:
        return
    user_key = _user_key(user.id, settings)
    log_event("deletion_requested", face=face.id)
    async with session_factory() as session:
        await repo.delete_user_data(session, user_key=user_key)
        await session.commit()

    language = await _language(state)
    await state.clear()
    await message.answer(t("data_deleted", language))
    log_event("deletion_completed", face=face.id)


@router.callback_query(F.data.startswith("lang:"))
async def on_language_chosen(callback: CallbackQuery, state: FSMContext, settings) -> None:
    language = callback.data.split(":", 1)[1]
    if language not in LANGUAGES:
        await callback.answer()
        return

    await state.update_data(language=language)
    await state.set_state(Onboarding.awaiting_consent)
    await _replace_or_send_consent_prompt(
        callback,
        language=language,
        notice_version=settings.notice_version,
    )
    log_event("consent_shown", language=language)
    await callback.answer()


@router.callback_query(F.data.startswith("consent:accept"))
async def on_consent_accepted(
    callback: CallbackQuery, state: FSMContext, settings, session_factory, face
) -> None:
    stored_language = (await state.get_data()).get("language", DEFAULT_LANGUAGE)
    language = parse_consent_callback(callback.data) or stored_language
    expected_callback = consent_callback_data(language, settings.notice_version)
    awaiting_consent = await state.get_state() == Onboarding.awaiting_consent.state
    if (
        not awaiting_consent
        or not callback.data
        or not hmac.compare_digest(callback.data, expected_callback)
    ):
        await state.update_data(language=language)
        await state.set_state(Onboarding.awaiting_consent)
        await callback.answer(t("consent_updated", language), show_alert=True)
        await _replace_or_send_consent_prompt(
            callback,
            language=language,
            notice_version=settings.notice_version,
        )
        return

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

    await state.update_data(language=language)
    await state.set_state(Onboarding.ready)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(entry_text(face.id, language))
    elif callback.bot is not None:
        await callback.bot.send_message(callback.from_user.id, entry_text(face.id, language))
    await callback.answer()
    log_event("consent_accepted", face=face.id, language=language)


async def _replace_or_send_consent_prompt(
    callback: CallbackQuery,
    *,
    language: str,
    notice_version: str,
) -> None:
    keyboard = consent_keyboard(language, notice_version)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            t("privacy_notice", language),
            reply_markup=keyboard,
        )
    elif callback.bot is not None:
        # The original message is too old to edit; send a fresh prompt so the
        # user can still reach the current consent button instead of being wedged.
        await callback.bot.send_message(
            callback.from_user.id,
            t("privacy_notice", language),
            reply_markup=keyboard,
        )


@router.callback_query(F.data.startswith("share:"))
async def on_share(callback: CallbackQuery, state: FSMContext, settings, session_factory) -> None:
    """Rebuild and offer a content-free Telegram share warning for a completed check."""

    raw_id = callback.data.split(":", 1)[1] if callback.data else ""
    try:
        check_id = UUID(raw_id)
    except ValueError:
        await callback.answer(t("share_expired", await _language(state)))
        return

    async with session_factory() as session:
        event = await repo.get_check_event(session, check_id)

    expected_user_key = _user_key(callback.from_user.id, settings)
    if event is None or not hmac.compare_digest(event.user_key, expected_user_key):
        await callback.answer(t("share_expired", await _language(state)))
        return

    language = event.language if event.language in LANGUAGES else await _language(state)
    summary = share_summary(list(event.rule_ids or []), language, event.face)
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("fb_share", language),
                    url=telegram_share_url(summary),
                )
            ]
        ]
    )
    log_event("share_clicked", face=event.face, language=language)
    await callback.answer()

    if isinstance(callback.message, Message):
        await callback.message.answer(summary, reply_markup=keyboard)
    elif callback.bot is not None:
        await callback.bot.send_message(callback.from_user.id, summary, reply_markup=keyboard)


@router.callback_query(F.data.startswith("fb:") | F.data.startswith("feedback:"))
async def on_feedback(
    callback: CallbackQuery, state: FSMContext, settings, session_factory, face
) -> None:
    language = await _language(state)
    parsed = parse_feedback_callback(callback.data)
    if parsed is None:
        await callback.answer(t("feedback_expired", language), show_alert=True)
        return

    kind, value, check_id = parsed
    expected_user_key = _user_key(callback.from_user.id, settings)
    async with session_factory() as session:
        event = await repo.get_check_event(session, check_id)
        authorized = (
            event is not None
            and event.face == face.id
            and event.status in {status.value for status in _FEEDBACK_STATUSES}
            and hmac.compare_digest(event.user_key, expected_user_key)
        )
        if not authorized:
            await callback.answer(t("feedback_expired", language), show_alert=True)
            return

        if event.language in LANGUAGES:
            language = event.language

        if kind == "usefulness":
            await repo.record_feedback(
                session,
                check_id=check_id,
                usefulness=value,
            )
            await session.commit()
        else:
            data = await state.get_data()
            usefulness = data.get("feedback_usefulness")
            feedback_check_id = data.get("feedback_check_id")
            if not usefulness or feedback_check_id != str(check_id):
                await callback.answer(t("feedback_usefulness_first", language), show_alert=True)
                return
            await repo.record_feedback(
                session,
                check_id=check_id,
                usefulness=usefulness,
                next_action=value,
            )
            await session.commit()

    if kind == "usefulness":
        await state.update_data(
            feedback_usefulness=value,
            feedback_check_id=str(check_id),
        )
        log_event("usefulness_answered", face=face.id, usefulness=value)
        await callback.answer(t("fb_saved", language))
        return

    log_event("decision_answered", face=face.id, next_action=value)
    await callback.answer(t("fb_saved", language))


@router.message()
async def on_content(
    message: Message, state: FSMContext, settings, session_factory, face
) -> None:
    """Run one check through the shared engine after confirming current consent (§12).

    Consent is re-read from the database on each message instead of trusting the
    in-memory FSM state, so a process restart can't wrongly block a user who has
    already consented, and bumping ``NOTICE_VERSION`` immediately forces
    re-consent. The engine never stores or echoes submitted content; only
    privacy-safe metadata is recorded.
    """

    user = message.from_user
    if user is None:
        return

    user_key = _user_key(user.id, settings)
    async with session_factory() as session:
        consent = await repo.get_consent(session, user_key=user_key, face=face.id)

    if not is_consent_current(consent, settings.notice_version):
        # Prefer the language recorded on any prior (possibly outdated) consent
        # row; FSM state is lost on restart and would wrongly default to Uzbek.
        language = consent.language if consent is not None else await _language(state)
        await message.answer(t("need_consent", language))
        return

    language = consent.language
    check_input = await _build_check_input(message, face=face, user_key=user_key, language=language)
    if check_input is None:
        await message.answer(t("unsupported_input", language))
        return

    async with session_factory() as session:
        result = await run_check(
            check_input,
            session=session,
            settings=settings,
            commit_rate_limit_reservation=True,
        )
        await session.commit()

    # Track the check id for the categorical feedback flow and clear any stale
    # usefulness from a previous check so it can't attach to this one.
    await state.update_data(
        last_check_id=str(result.check_id) if result.check_id else None,
        feedback_usefulness=None,
        feedback_check_id=None,
    )
    keyboard = (
        post_check_keyboard(language, result.check_id)
        if result.status in _FEEDBACK_STATUSES
        else None
    )
    await message.answer(result.text or t("unsupported_input", language), reply_markup=keyboard)


async def _build_check_input(
    message: Message, *, face: Face, user_key: str, language: str
) -> CheckInput | None:
    """Build a CheckInput from a photo or text message, or None if unsupported."""

    lang = Language(language)
    if message.photo:
        image_bytes = await _download_photo(message)
        if not image_bytes:
            return None
        return CheckInput(
            face=face.id,
            user_key=user_key,
            language=lang,
            input_type=InputType.image,
            image_bytes=image_bytes,
            caption=message.caption,
        )

    text = message.text or message.caption
    if text and text.strip():
        return CheckInput(
            face=face.id,
            user_key=user_key,
            language=lang,
            input_type=InputType.text,
            raw_text=text,
        )
    return None


async def _download_photo(message: Message) -> bytes | None:
    """Download the largest available photo size into memory."""

    if message.bot is None or not message.photo:
        return None
    buffer = BytesIO()
    await message.bot.download(message.photo[-1], destination=buffer)
    return buffer.getvalue() or None
