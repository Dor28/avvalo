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


def post_check_keyboard(share_url: str = DEFAULT_SHARE_URL) -> InlineKeyboardMarkup:
    """Categorical feedback buttons plus a content-free Telegram share link."""

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Useful", callback_data="feedback:usefulness:yes"),
                InlineKeyboardButton(text="Partly", callback_data="feedback:usefulness:partly"),
                InlineKeyboardButton(text="No", callback_data="feedback:usefulness:no"),
            ],
            [
                InlineKeyboardButton(text="Verify", callback_data="feedback:next_action:verify"),
                InlineKeyboardButton(text="Stop", callback_data="feedback:next_action:delay_stop"),
            ],
            [
                InlineKeyboardButton(
                    text="Continue", callback_data="feedback:next_action:continue"
                ),
                InlineKeyboardButton(
                    text="Not sure", callback_data="feedback:next_action:not_sure"
                ),
            ],
            [InlineKeyboardButton(text="Share Avvalo", url=share_url)],
        ]
    )
