"""Build strict or answer-prompt-safe views of ephemeral submitted text."""

from __future__ import annotations

import re

from app.engine.url import URL_RE, classify_link, split_url_trailing_punctuation

_EMAIL_RE = re.compile(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b")
_TME_RE = re.compile(r"(?i)\b(?:https?|hxxps?)://t\.me/[a-z0-9_]{4,32}\b")
_HANDLE_RE = re.compile(r"(?<!\w)@[a-z0-9_]{4,32}\b", re.IGNORECASE)
# Match explicit international numbers first, then common Uzbek local/mobile
# formatting. Requiring ``+`` on the generic branch avoids treating dates and
# spaced monetary amounts as phone numbers.
_PHONE_RE = re.compile(
    r"(?<!\d)(?:"
    r"\+\d{1,3}(?:[\s().-]*\d){6,14}"
    r"|(?:\+?998[\s().-]?)?(?:\(?[2-9]\d\)?[\s().-]?)\d{3}"
    r"[\s().-]?\d{2}[\s().-]?\d{2}"
    r")(?!\d)"
)
_CODE_VALUE_RE = re.compile(
    r"(?iu)\b((?:sms\s*)?(?:otp|kod|code|код|parol|пароль?|password)[^\d]{0,20})"
    r"(\d{4,8})(?!\d)"
)
_SECRET_VALUE_RE = re.compile(
    r"(?iu)\b((?:password|parol|пароль?)(?:\s+(?:is|bu|это))?"
    r"[ \t:=\-\u2013\u2014]{1,10})(\S{3,128})"
)
_PASSPORT_RE = re.compile(r"(?i)(?<![a-z0-9])(?:[a-z]{2}\s?\d{7})(?![a-z0-9])")
_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
_ADDRESS_RE = re.compile(
    "(?iu)\\b(?:ko['\\u2018\\u2019]chasi|\\u043a\\u0443\\u0447\\u0430\\u0441\\u0438|"
    "\\u043a\\u045e\\u0447\\u0430\\u0441\\u0438|\\u0443\\u043b\\u0438\\u0446\\u0430|"
    "\\u0443\\u043b\\.|street|st\\.)\\s+[^\\n,.;]{2,50}\\d*"
)
_NAME_UPPER = "A-Z\\u0410-\\u042f\\u0401\\u040e\\u049a\\u0492\\u04b2"
_NAME_LOWER = "a-z\\u0430-\\u044f\\u0451\\u045e\\u049b\\u0493\\u04b3"
_NAME_RE = re.compile(
    "(?<![\\w\\[])"
    f"(?:[{_NAME_UPPER}][{_NAME_LOWER}']{{2,}}\\s+){{1,2}}"
    f"[{_NAME_UPPER}][{_NAME_LOWER}']{{2,}}"
    "(?![\\w\\]])"
)


def minimize(
    raw_text: str,
    *,
    preserve_names: bool = False,
    preserve_urls: bool = False,
) -> str:
    """Replace protected identifiers while keeping useful situation wording.

    The strict default remains suitable for retrieval and routing. The answer
    prompt may deliberately preserve submitted names and URLs, but every other
    protected value is still tokenized and no mapping or submitted value is
    persisted or logged.
    """

    if preserve_urls:
        return _minimize_around_urls(raw_text, preserve_names=preserve_names)
    return _minimize_protected_values(raw_text, preserve_names=preserve_names)


def _minimize_around_urls(raw_text: str, *, preserve_names: bool) -> str:
    """Minimize non-URL spans without altering any character inside a URL."""

    chunks: list[str] = []
    cursor = 0
    for match in URL_RE.finditer(raw_text):
        # The bare-host branch also matches the domain half of an email. Keep
        # that match inside the non-URL span so the whole email is tokenized.
        if match.start() > 0 and raw_text[match.start() - 1] == "@":
            continue
        chunks.append(
            _minimize_protected_values(raw_text[cursor : match.start()], preserve_names)
        )
        chunks.append(match.group(0))
        cursor = match.end()
    chunks.append(_minimize_protected_values(raw_text[cursor:], preserve_names))
    return "".join(chunks)


def _minimize_protected_values(raw_text: str, preserve_names: bool) -> str:
    minimized = _EMAIL_RE.sub("[EMAIL]", raw_text)
    minimized = _TME_RE.sub("[HANDLE]", minimized)
    minimized = URL_RE.sub(_replace_link, minimized)
    minimized = _HANDLE_RE.sub("[HANDLE]", minimized)
    minimized = _PHONE_RE.sub("[PHONE]", minimized)
    minimized = _SECRET_VALUE_RE.sub(lambda match: f"{match.group(1)}[SECRET]", minimized)
    minimized = _CODE_VALUE_RE.sub(lambda match: f"{match.group(1)}[CODE]", minimized)
    minimized = _PASSPORT_RE.sub("[PASSPORT]", minimized)
    minimized = _CARD_RE.sub(_replace_card, minimized)
    minimized = _ADDRESS_RE.sub("[ADDRESS]", minimized)
    if not preserve_names:
        minimized = _NAME_RE.sub("[NAME]", minimized)
    return minimized


def _replace_link(match: re.Match[str]) -> str:
    value = match.group(0)
    core, suffix = split_url_trailing_punctuation(value)
    label = classify_link(core)
    token = f"[LINK: {label}]" if label else "[LINK]"
    return f"{token}{suffix}"


def _replace_card(match: re.Match[str]) -> str:
    value = match.group(0)
    digits = re.sub(r"\D", "", value)
    if 13 <= len(digits) <= 19:
        return "[CARD]"
    return value
