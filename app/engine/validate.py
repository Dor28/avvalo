"""Deterministic safety validation for LLM drafts."""

from __future__ import annotations

import re

from pydantic import BaseModel

from app.engine.types import DraftOutput, Language, RuleHit, Signal

_MAX_BULLETS = 3

_BANNED_WORDS = {
    Language.ru: (
        "безопасно",
        "мошенник",
        "аферист",
        "афёрист",
        "надежный",
        "надёжный",
        "законно",
    ),
    Language.uz_latn: ("xavfsiz", "firibgar", "ishonchli", "qonuniy"),
    Language.uz_cyrl: ("хавфсиз", "фирибгар", "ишончли", "қонуний"),
}
_EN_BANNED = (
    "safe",
    "verified",
    "legitimate",
    "not a scam",
    "scammer",
    "fraudster",
    "fraud confirmed",
    "fraud",
)

_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?\d[\d\s().-]{6,}\d)(?!\d)",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b")
_URL_OR_DOMAIN_RE = re.compile(
    r"(?ix)"
    r"\b(?:https?|hxxps?)://[^\s<>()]+"
    r"|\bwww\.[a-z0-9.-]+\.[a-z]{2,}(?:/[^\s<>()]*)?"
    r"|\b[a-z0-9][a-z0-9-]{1,63}(?:\.[a-z0-9-]{1,63})+\.[a-z]{2,}"
    r"(?:/[^\s<>()]*)?"
)
_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
_OTP_LABELED_RE = re.compile(
    r"(?iu)\b(?:otp|sms\s*code|sms\s*kod|kod|code|код|смс\s*код)[^\d]{0,20}\d{4,8}(?!\d)"
)
_PASSWORD_VALUE_RE = re.compile(
    r"(?iu)\b(?:password|parol|пароль)[\s:=\-]{0,10}\S{3,}"
)

_UNSAFE_PATTERNS = (
    r"(?i)\b(?:open|click|follow|visit)\s+(?:the\s+)?(?:link|url)\b",
    r"(?i)\bscan\s+(?:the\s+)?qr\b",
    r"(?i)\b(?:call|text|write|message)\s+(?:the\s+)?(?:number|phone)"
    r"\s+(?:from|in|inside)\s+(?:the\s+)?message\b",
    r"(?i)\breply\s+(?:to\s+)?(?:check|test)\b",
    r"(?iu)\b(?:откройте|открой|перейдите|перейди|нажмите|нажми)\s+"
    r"(?:по\s+)?(?:ссылк[ауе]|линк)\b",
    r"(?iu)\b(?:отсканируйте|сканируйте|сканируй)\s+(?:qr|qr-код|код)\b",
    r"(?iu)\b(?:позвоните|позвони|напишите|напиши)\s+"
    r"(?:на\s+)?(?:номер|телефон)\s+(?:из|в)\s+(?:сообщени[яие]|чата)\b",
    r"(?iu)\b(?:ответьте|ответь)\s+(?:чтобы\s+)?(?:проверить|протестировать)\b",
    r"(?i)\b(?:linkni|havolani)\s+(?:och|oching|bosing)\b",
    r"(?i)\bqr\s*(?:kodni|kodingizni)?\s*(?:skanerlang|skaner qil)\b",
    r"(?i)\b(?:xabardagi|chatdagi)\s+(?:raqam|telefon)(?:ga)?\s+"
    r"(?:qo'ng'iroq|qongiroq|yoz)\b",
    r"(?iu)\b(?:линкни|ҳаволани|хаволани)\s+(?:очинг|босинг)\b",
    r"(?iu)\bqr\s*(?:кодни)?\s*(?:сканерланг|сканер қилинг)\b",
    r"(?iu)\b(?:хабардаги|чатдаги)\s+(?:рақам|телефон)(?:га)?\s+"
    r"(?:қўнғироқ|ёз)\b",
)


class ValidationResult(BaseModel):
    """Result of deterministic draft validation."""

    ok: bool
    draft: DraftOutput
    reason: str | None = None
    no_signal: bool = False


def validate(
    draft: DraftOutput,
    signals: list[Signal],
    rule_hits: list[RuleHit],
    language: Language,
) -> ValidationResult:
    """Validate and normalize one LLM draft."""

    _ = signals
    normalized = _truncate_blocks(draft)
    no_signal = len(rule_hits) == 0 and len(normalized.red_flags) == 0
    text = _joined_text(normalized)

    reason = _first_rejection_reason(text, normalized, no_signal, language)
    return ValidationResult(
        ok=reason is None,
        draft=normalized,
        reason=reason,
        no_signal=no_signal,
    )


def _truncate_blocks(draft: DraftOutput) -> DraftOutput:
    return draft.model_copy(
        update={
            "red_flags": list(draft.red_flags[:_MAX_BULLETS]),
            "verify": list(draft.verify[:_MAX_BULLETS]),
            "ask": list(draft.ask[:_MAX_BULLETS]),
        }
    )


def _joined_text(draft: DraftOutput) -> str:
    parts = [*draft.red_flags, draft.pattern or "", *draft.verify, *draft.ask]
    return "\n".join(part for part in parts if part).strip()


def _first_rejection_reason(
    text: str, draft: DraftOutput, no_signal: bool, language: Language
) -> str | None:
    lower = text.casefold()
    banned = (*_BANNED_WORDS[language], *_EN_BANNED)
    for word in banned:
        if re.search(rf"(?<![\w-]){re.escape(word.casefold())}(?![\w-])", lower):
            return f"banned verdict word: {word}"

    if _EMAIL_RE.search(text) or _URL_OR_DOMAIN_RE.search(text):
        return "raw contact or URL leaked"
    if _PHONE_RE.search(text):
        return "raw phone number leaked"
    if _CARD_RE.search(text):
        return "raw card/account number leaked"
    if _OTP_LABELED_RE.search(text) or _PASSWORD_VALUE_RE.search(text):
        return "secret value leaked"
    for pattern in _UNSAFE_PATTERNS:
        if re.search(pattern, text):
            return "unsafe instruction to use suspicious contact path"
    if not draft.verify:
        return "verify block is empty"
    if not draft.ask:
        return "ask block is empty"
    if not no_signal and not draft.red_flags:
        return "red_flags block is empty despite detected signals"
    return None
