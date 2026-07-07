"""Telegram handlers: onboarding, consent, privacy, and deletion (§12).

No handler stores or echoes submitted content. The consent gate ensures content
is only accepted after the current privacy notice has been agreed to.
"""

import logging
from io import BytesIO
from uuid import UUID

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.keyboards import (
    consent_keyboard,
    language_keyboard,
    post_check_keyboard,
    story_invite_keyboard,
    story_publish_keyboard,
    telegram_share_url,
)
from app.bot.states import Onboarding, StoryCapture
from app.bot.texts import DEFAULT_LANGUAGE, LANGUAGES, entry_text, t
from app.config import Settings
from app.data import repo
from app.engine import CheckInput, CheckStatus, InputType, Language, run_check
from app.engine.faces import Face
from app.engine.format import share_summary
from app.engine.minimize import minimize
from app.engine.rules import run_rules
from app.obs.events import log_event
from app.privacy.consent import grant_consent, is_consent_current
from app.privacy.user_key import derive_user_key

_FEEDBACK_STATUSES = {CheckStatus.ok, CheckStatus.no_signal}
LOGGER = logging.getLogger(__name__)

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
        t("choose_language", DEFAULT_LANGUAGE),
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
async def on_language_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    language = callback.data.split(":", 1)[1]
    if language not in LANGUAGES:
        await callback.answer()
        return

    await state.update_data(language=language)
    await state.set_state(Onboarding.awaiting_consent)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            t("privacy_notice", language),
            reply_markup=consent_keyboard(language),
        )
    elif callback.bot is not None:
        # The original message is too old to edit; send a fresh prompt so the
        # user can still reach the consent button instead of being wedged.
        await callback.bot.send_message(
            callback.from_user.id,
            t("privacy_notice", language),
            reply_markup=consent_keyboard(language),
        )
    log_event("consent_shown", language=language)
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
    if isinstance(callback.message, Message):
        await callback.message.edit_text(entry_text(face.id, language))
    elif callback.bot is not None:
        await callback.bot.send_message(callback.from_user.id, entry_text(face.id, language))
    await callback.answer()
    log_event("consent_accepted", face=face.id, language=language)


@router.callback_query(F.data.startswith("share:"))
async def on_share(callback: CallbackQuery, state: FSMContext, session_factory) -> None:
    """Rebuild and offer a content-free Telegram share warning for a completed check."""

    raw_id = callback.data.split(":", 1)[1] if callback.data else ""
    try:
        check_id = UUID(raw_id)
    except ValueError:
        await callback.answer(t("share_expired", await _language(state)))
        return

    async with session_factory() as session:
        event = await repo.get_check_event(session, check_id)

    if event is None:
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


@router.callback_query(F.data.startswith("story:"))
async def on_story_callback(
    callback: CallbackQuery, state: FSMContext, settings, session_factory, face
) -> None:
    action = callback.data.split(":", 1)[1] if callback.data else ""
    language = await _language(state)

    if action == "cancel":
        await _clear_story_state(state, language=language)
        await callback.answer(t("story_cancelled", language))
        await _send_user_message(callback, t("story_cancelled", language))
        return

    if action == "start":
        data = await state.get_data()
        if not data.get("story_check_id"):
            await callback.answer(t("story_expired", language))
            return
        user_key = _user_key(callback.from_user.id, settings)
        if await _story_limit_reached(session_factory, user_key=user_key, settings=settings):
            await _clear_story_state(state, language=language)
            await callback.answer(t("story_limit_reached", language))
            await _send_user_message(callback, t("story_limit_reached", language))
            return
        await state.set_state(StoryCapture.awaiting_story)
        await callback.answer()
        await _send_user_message(callback, t("story_prompt", language))
        return

    if action != "publish":
        await callback.answer()
        return

    data = await state.get_data()
    raw_text = data.get("story_raw_text")
    story_face = data.get("story_face") or face.id
    story_language = data.get("story_language") or language
    if not raw_text:
        await _clear_story_state(state, language=language)
        await callback.answer(t("story_expired", language))
        return

    user_key = _user_key(callback.from_user.id, settings)
    if await _story_limit_reached(session_factory, user_key=user_key, settings=settings):
        await _clear_story_state(state, language=language)
        await callback.answer(t("story_limit_reached", language))
        await _send_user_message(callback, t("story_limit_reached", language))
        return

    async with session_factory() as session:
        story = await repo.store_story(
            session,
            user_key=user_key,
            face=story_face,
            language=story_language,
            raw_text=raw_text,
        )
        await session.commit()

    await _forward_story_to_operator(callback, settings=settings, story=story)
    await _clear_story_state(state, language=story_language)
    log_event("story_submitted", face=story_face, language=story_language)
    await callback.answer(t("story_saved", story_language))
    await _send_user_message(callback, t("story_saved", story_language))


@router.callback_query(F.data.startswith("feedback:"))
async def on_feedback(callback: CallbackQuery, state: FSMContext, session_factory, face) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer()
        return

    _, kind, value = parts
    language = await _language(state)
    if kind == "usefulness":
        if value not in repo.USEFULNESS_VALUES:
            await callback.answer()
            return
        data = await state.get_data()
        check_id = data.get("last_check_id")
        if check_id:
            async with session_factory() as session:
                await repo.record_feedback(
                    session,
                    check_id=UUID(str(check_id)),
                    usefulness=value,
                )
                await session.commit()
        story_data = {}
        if check_id and value in {"yes", "partly"}:
            story_data = {
                "story_check_id": str(check_id),
                "story_face": face.id,
                "story_language": language,
            }
        await state.update_data(feedback_usefulness=value, **story_data)
        log_event("usefulness_answered", face=face.id, usefulness=value)
        await callback.answer(t("fb_saved", language))
        if story_data:
            await _send_user_message(
                callback,
                t("story_invite", language),
                reply_markup=story_invite_keyboard(language),
            )
        return

    if kind != "next_action":
        await callback.answer()
        return
    if value not in repo.NEXT_ACTION_VALUES:
        await callback.answer()
        return

    data = await state.get_data()
    usefulness = data.get("feedback_usefulness")
    check_id = data.get("last_check_id")
    if usefulness and check_id:
        async with session_factory() as session:
            await repo.record_feedback(
                session,
                check_id=UUID(str(check_id)),
                usefulness=usefulness,
                next_action=value,
            )
            await session.commit()

    log_event("decision_answered", face=face.id, next_action=value)
    await callback.answer(t("fb_saved", language))


@router.message(StoryCapture.awaiting_story)
async def on_story_text(
    message: Message, state: FSMContext, settings, face
) -> None:
    language = await _language(state)
    text = (message.text or "").strip()
    if not text:
        await message.answer(t("story_text_required", language))
        return
    if len(text) > settings.story_max_chars:
        await message.answer(
            t("story_too_long", language).format(limit=settings.story_max_chars)
        )
        return

    story_face = face.id
    _, signals = run_rules(text, story_face)
    minimized_text = minimize(text, signals).strip()
    await state.update_data(
        story_raw_text=text,
        story_minimized_text=minimized_text,
        story_face=story_face,
        story_language=language,
    )
    await state.set_state(StoryCapture.awaiting_publish)
    await message.answer(
        _story_preview_text(language, minimized_text),
        reply_markup=story_publish_keyboard(language),
    )


@router.message(StoryCapture.awaiting_publish)
async def on_story_publish_waiting(message: Message, state: FSMContext) -> None:
    language = await _language(state)
    await message.answer(
        _story_preview_text(language, (await state.get_data()).get("story_minimized_text", "")),
        reply_markup=story_publish_keyboard(language),
    )


async def _send_user_message(
    callback: CallbackQuery, text: str, *, reply_markup: InlineKeyboardMarkup | None = None
) -> None:
    if isinstance(callback.message, Message):
        await callback.message.answer(text, reply_markup=reply_markup)
    elif callback.bot is not None:
        await callback.bot.send_message(
            callback.from_user.id, text, reply_markup=reply_markup
        )


async def _clear_story_state(state: FSMContext, *, language: str) -> None:
    data = await state.get_data()
    kept = {"language": language}
    for key in ("last_check_id", "feedback_usefulness"):
        if data.get(key) is not None:
            kept[key] = data[key]
    await state.set_data(kept)
    await state.set_state(Onboarding.ready)


def _story_preview_text(language: str, minimized_text: str) -> str:
    return (
        f"{t('story_preview_intro', language)}\n\n"
        f"{minimized_text}\n\n"
        f"{t('story_preview_confirm', language)}"
    )


async def _story_limit_reached(session_factory, *, user_key: str, settings: Settings) -> bool:
    async with session_factory() as session:
        count = await repo.count_story_submissions_for_day(session, user_key=user_key)
    return count >= settings.story_daily_limit


async def _forward_story_to_operator(
    callback: CallbackQuery, *, settings: Settings, story
) -> None:
    if not settings.operator_alert_chat_id:
        LOGGER.warning("story operator forward skipped: OPERATOR_ALERT_CHAT_ID unset")
        return
    if callback.bot is None:
        LOGGER.warning(
            "story operator forward skipped: callback bot missing story_id=%s", story.id
        )
        return
    try:
        await callback.bot.send_message(
            settings.operator_alert_chat_id,
            _operator_story_text(story),
        )
    except Exception as exc:  # pragma: no cover - defensive around Telegram IO
        LOGGER.warning(
            "story operator forward failed story_id=%s error_type=%s",
            story.id,
            exc.__class__.__name__,
        )


def _operator_story_text(story) -> str:
    return (
        "Avvalo story submission\n"
        f"id: {story.id}\n"
        f"face: {story.face}\n"
        f"language: {story.language}\n"
        f"status: {story.status}\n\n"
        f"{story.minimized_text}\n\n"
        f"Review: python tools/stories.py approve {story.id}"
    )


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
        result = await run_check(check_input, session=session, settings=settings)
        await session.commit()

    # Track the check id for the categorical feedback flow and clear any stale
    # usefulness from a previous check so it can't attach to this one.
    await state.update_data(
        last_check_id=str(result.check_id) if result.check_id else None,
        feedback_usefulness=None,
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
