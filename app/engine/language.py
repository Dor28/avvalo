"""Content-language resolution for analysis and replies."""

from __future__ import annotations

import re

from app.engine.types import Language

_CYRILLIC_WORD_RE = re.compile(r"[\u0400-\u04ff]+")
_LATIN_WORD_RE = re.compile(r"[A-Za-z\u02bc']+")
_UZ_CYRL_MARKER_RE = re.compile(r"[\u040e\u045e\u0492\u0493\u049a\u049b\u04b2\u04b3]")

_UZ_LATN_MARKERS = (
    " o'",
    " g'",
    " sh",
    " ch",
    " xavf",
    " yubor",
    " tekshir",
    " so'm",
    " to'lov",
    " bugun",
    " hozir",
    " uchun",
    " kart",
    " hisob",
)

_UZ_CYRL_WORDS = (
    "\u0445\u0430\u0432\u0444",
    "\u0442\u0435\u043a\u0448\u0438\u0440",
    "\u044e\u0431\u043e\u0440",
    "\u0443\u0447\u0443\u043d",
    "\u0431\u0443\u0433\u0443\u043d",
    "\u04b3\u043e\u0437\u0438\u0440",
    "\u0442\u045e\u043b\u043e\u0432",
    "\u0441\u045e\u043c",
    "\u043a\u0430\u0440\u0442\u0430",
)


def resolve_content_language(text: str, *, fallback: Language) -> Language:
    """Return the dominant supported reply language for *text*.

    The detector is intentionally conservative and local: script majority wins
    first, Uzbek-specific markers split Uzbek from Russian, and ``langdetect``
    is used only as an optional extra signal.

    Cyrillic-Uzbek is still detected — it must not be mistaken for Russian —
    but Uzbek is only ever answered in Latin script, so it resolves to
    :attr:`Language.uz_latn`.
    """

    normalized = f" {text.casefold()} "
    cyrillic_words = _CYRILLIC_WORD_RE.findall(normalized)
    latin_words = _LATIN_WORD_RE.findall(normalized)

    if len(cyrillic_words) > len(latin_words):
        return _resolve_cyrillic(normalized, fallback=fallback)
    if len(latin_words) > len(cyrillic_words):
        return _resolve_latin(normalized, fallback=fallback)
    return fallback


def _resolve_cyrillic(text: str, *, fallback: Language) -> Language:
    if _UZ_CYRL_MARKER_RE.search(text) or any(marker in text for marker in _UZ_CYRL_WORDS):
        return Language.uz_latn
    detected = _langdetect(text)
    if detected == "ru":
        return Language.ru
    if detected == "uz":
        return Language.uz_latn
    return Language.ru if fallback is Language.uz_latn else fallback


def _resolve_latin(text: str, *, fallback: Language) -> Language:
    if any(marker in text for marker in _UZ_LATN_MARKERS):
        return Language.uz_latn
    detected = _langdetect(text)
    if detected == "uz":
        return Language.uz_latn
    return fallback


def _langdetect(text: str) -> str | None:
    try:
        from langdetect import LangDetectException, detect_langs

        ranked = detect_langs(text)
    except (ImportError, LangDetectException):
        return None

    if not ranked:
        return None
    top = ranked[0]
    if top.prob < 0.75:
        return None
    return top.lang
