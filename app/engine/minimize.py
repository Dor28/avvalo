"""Text minimization before any model call."""

from __future__ import annotations

import re

from app.engine.rules.engine import classify_link
from app.engine.types import Signal

_EMAIL_RE = re.compile(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b")
_TME_RE = re.compile(r"(?i)\b(?:https?|hxxps?)://t\.me/[a-z0-9_]{4,32}\b")
_URL_RE = re.compile(
    r"(?ix)"
    r"\b(?:https?|hxxps?)://[^\s<>()]+"
    r"|\b(?:www\.)?[a-z0-9][a-z0-9.-]*(?:\.|\[\.\]|\(\.\))[a-z]{2,}"
    r"(?:/[^\s<>()]*)?"
)
_HANDLE_RE = re.compile(r"(?<!\w)@[a-z0-9_]{4,32}\b", re.IGNORECASE)
# The operator-code group accepts any valid two-digit Uzbek mobile prefix
# (20, 33, 50, 55, 77, 88, 90-99, …), not only those starting with 3/6/7/9 —
# missing 50/55/88/20 leaked raw numbers past minimization into the prompt.
_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?998[\s().-]?)?(?:\(?[2-9]\d\)?[\s().-]?)\d{3}"
    r"[\s().-]?\d{2}[\s().-]?\d{2}(?!\d)"
)
_CODE_VALUE_RE = re.compile(
    r"(?iu)\b((?:sms\s*)?(?:otp|kod|code|код|парол|password)[^\d]{0,20})"
    r"(\d{4,8})(?!\d)"
)
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


def minimize(raw_text: str, signals: list[Signal] | None = None) -> str:
    """Replace raw identifiers with typed tokens while keeping scam wording."""

    _ = signals
    minimized = _EMAIL_RE.sub("[EMAIL]", raw_text)
    minimized = _TME_RE.sub("[HANDLE]", minimized)
    minimized = _URL_RE.sub(_replace_link, minimized)
    minimized = _HANDLE_RE.sub("[HANDLE]", minimized)
    minimized = _PHONE_RE.sub("[PHONE]", minimized)
    minimized = _CODE_VALUE_RE.sub(lambda match: f"{match.group(1)}[CODE]", minimized)
    minimized = _CARD_RE.sub(_replace_card, minimized)
    minimized = _ADDRESS_RE.sub("[ADDRESS]", minimized)
    minimized = _NAME_RE.sub("[NAME]", minimized)
    return minimized


def _replace_link(match: re.Match[str]) -> str:
    value = match.group(0)
    core = value.rstrip(".,;:!?)]}\"'")
    suffix = value[len(core) :]
    label = classify_link(core)
    token = f"[LINK: {label}]" if label else "[LINK]"
    return f"{token}{suffix}"


def _replace_card(match: re.Match[str]) -> str:
    value = match.group(0)
    digits = re.sub(r"\D", "", value)
    if 13 <= len(digits) <= 19:
        return "[CARD]"
    return value
