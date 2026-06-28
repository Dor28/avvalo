"""Inline keyboards for onboarding, consent, and post-check feedback."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.texts import LANGUAGE_LABELS, LANGUAGES, t

DEFAULT_SHARE_URL = "https://t.me/share/url?text=Avvalo"


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
    language: str, share_url: str = DEFAULT_SHARE_URL
) -> InlineKeyboardMarkup:
    """Localized categorical feedback buttons plus a content-free share link."""

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
            [InlineKeyboardButton(text=t("fb_share", language), url=share_url)],
        ]
    )
