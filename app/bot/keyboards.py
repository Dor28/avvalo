"""Inline keyboards for onboarding, consent, post-check feedback, and sharing."""

from hashlib import sha256
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


_CONSENT_LANGUAGE_CODES = {"uz_latn": "l", "uz_cyrl": "c", "ru": "r"}
_CONSENT_LANGUAGES = {code: language for language, code in _CONSENT_LANGUAGE_CODES.items()}


def consent_callback_data(language: str, notice_version: str) -> str:
    """Bind a compact Telegram callback to the notice and language shown."""

    language_code = _CONSENT_LANGUAGE_CODES[language]
    version_token = sha256(f"{language}:{notice_version}".encode()).hexdigest()[:16]
    return f"consent:accept:{language_code}:{version_token}"


def parse_consent_callback(data: str | None) -> str | None:
    """Return the notice language encoded by a current-format callback."""

    parts = (data or "").split(":")
    if len(parts) != 4 or parts[:2] != ["consent", "accept"]:
        return None
    return _CONSENT_LANGUAGES.get(parts[2])


def consent_keyboard(language: str, notice_version: str) -> InlineKeyboardMarkup:
    """A single "I agree" button bound to the displayed notice version."""

    button = InlineKeyboardButton(
        text=t("btn_agree", language),
        callback_data=consent_callback_data(language, notice_version),
    )
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


_FEEDBACK_CODES = {
    ("usefulness", "yes"): ("u", "y"),
    ("usefulness", "partly"): ("u", "p"),
    ("usefulness", "no"): ("u", "n"),
    ("next_action", "verify"): ("a", "v"),
    ("next_action", "delay_stop"): ("a", "s"),
    ("next_action", "continue"): ("a", "c"),
    ("next_action", "not_sure"): ("a", "n"),
}
_FEEDBACK_VALUES = {codes: values for values, codes in _FEEDBACK_CODES.items()}


def feedback_callback_data(kind: str, value: str, check_id: UUID | str) -> str:
    """Return a compact callback bound to one check event."""

    kind_code, value_code = _FEEDBACK_CODES[(kind, value)]
    return f"fb:{kind_code}:{value_code}:{UUID(str(check_id))}"


def parse_feedback_callback(data: str | None) -> tuple[str, str, UUID] | None:
    """Parse only the current check-bound feedback callback format."""

    parts = (data or "").split(":")
    if len(parts) != 4 or parts[0] != "fb":
        return None
    values = _FEEDBACK_VALUES.get((parts[1], parts[2]))
    if values is None:
        return None
    try:
        check_id = UUID(parts[3])
    except ValueError:
        return None
    return *values, check_id


def post_check_keyboard(
    language: str, check_id: UUID | str | None = None, share_url: str = DEFAULT_SHARE_URL
) -> InlineKeyboardMarkup:
    """Localized, check-bound feedback buttons plus a content-free share action."""

    share_button = (
        InlineKeyboardButton(text=t("fb_share", language), callback_data=f"share:{check_id}")
        if check_id
        else InlineKeyboardButton(text=t("fb_share", language), url=share_url)
    )

    feedback_rows = (
        [
            [
                InlineKeyboardButton(
                    text=t("fb_useful", language),
                    callback_data=feedback_callback_data("usefulness", "yes", check_id),
                ),
                InlineKeyboardButton(
                    text=t("fb_partly", language),
                    callback_data=feedback_callback_data("usefulness", "partly", check_id),
                ),
                InlineKeyboardButton(
                    text=t("fb_not_useful", language),
                    callback_data=feedback_callback_data("usefulness", "no", check_id),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("fb_verify", language),
                    callback_data=feedback_callback_data("next_action", "verify", check_id),
                ),
                InlineKeyboardButton(
                    text=t("fb_stop", language),
                    callback_data=feedback_callback_data("next_action", "delay_stop", check_id),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=t("fb_continue", language),
                    callback_data=feedback_callback_data("next_action", "continue", check_id),
                ),
                InlineKeyboardButton(
                    text=t("fb_not_sure", language),
                    callback_data=feedback_callback_data("next_action", "not_sure", check_id),
                ),
            ],
        ]
        if check_id is not None
        else []
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            *feedback_rows,
            [share_button],
        ]
    )
