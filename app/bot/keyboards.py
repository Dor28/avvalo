"""Inline keyboards for onboarding and consent."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.texts import LANGUAGE_LABELS, LANGUAGES, t


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
