"""Inline keyboards for onboarding, consent, post-check feedback, and sharing."""

from urllib.parse import urlencode
from uuid import UUID

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.texts import LANGUAGE_LABELS, LANGUAGES, t

BOT_LINK = "https://t.me/Avvalo_official_bot"


def telegram_share_url(text: str = "Avvalo") -> str:
    """Build a Telegram share URL without embedding submitted content."""

    return "https://t.me/share/url?" + urlencode({"url": BOT_LINK, "text": text})


DEFAULT_SHARE_URL = telegram_share_url()


def language_keyboard() -> InlineKeyboardMarkup:
    """One button per supported language; callback data is ``lang:<code>``."""

    rows = [
        [InlineKeyboardButton(text=LANGUAGE_LABELS[language], callback_data=f"lang:{language}")]
        for language in LANGUAGES
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def consent_keyboard(language: str) -> InlineKeyboardMarkup:
    """A single "I agree" button; callback data is ``consent:accept``."""

    button = InlineKeyboardButton(text=t("btn_agree", language), callback_data="consent:accept")
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


def post_check_keyboard(
    language: str, check_id: UUID | str | None = None, share_url: str = DEFAULT_SHARE_URL
) -> InlineKeyboardMarkup:
    """Localized categorical feedback buttons plus a content-free share action."""

    share_button = (
        InlineKeyboardButton(text=t("fb_share", language), callback_data=f"share:{check_id}")
        if check_id
        else InlineKeyboardButton(text=t("fb_share", language), url=share_url)
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("fb_useful", language), callback_data="feedback:usefulness:yes"
                ),
                InlineKeyboardButton(
                    text=t("fb_partly", language), callback_data="feedback:usefulness:partly"
                ),
                InlineKeyboardButton(
                    text=t("fb_not_useful", language), callback_data="feedback:usefulness:no"
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("fb_verify", language), callback_data="feedback:next_action:verify"
                ),
                InlineKeyboardButton(
                    text=t("fb_stop", language),
                    callback_data="feedback:next_action:delay_stop",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("fb_continue", language),
                    callback_data="feedback:next_action:continue",
                ),
                InlineKeyboardButton(
                    text=t("fb_not_sure", language),
                    callback_data="feedback:next_action:not_sure",
                ),
            ],
            [share_button],
        ]
    )
