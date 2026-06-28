"""Telegram handlers: onboarding, consent, privacy, and deletion (§12).

No handler stores or echoes submitted content. The consent gate ensures content
is only accepted after the current privacy notice has been agreed to.
"""

from io import BytesIO
from uuid import UUID

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import consent_keyboard, language_keyboard, post_check_keyboard
from app.bot.states import Onboarding
from app.bot.texts import DEFAULT_LANGUAGE, LANGUAGES, entry_text, t
from app.config import Settings
from app.data import repo
from app.engine import CheckInput, CheckStatus, InputType, Language, run_check
from app.engine.faces import Face
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
        await state.update_data(feedback_usefulness=value)
        log_event("usefulness_answered", face=face.id, usefulness=value)
        await callback.answer(t("fb_saved", language))
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
    keyboard = post_check_keyboard(language) if result.status in _FEEDBACK_STATUSES else None
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
