"""Detect conversational chatter that is not a situation to check (V1_TECHNICAL_PLAN §5.1).

Every message reaching the pipeline used to be forced through the fraud-check
prompt, so a greeting or a "what can you do" question came back formatted as
if it were a suspicious situation with nothing found. This module short-circuits
that class of message deterministically, before any rule or LLM call runs.

Matching is an exact (post-normalization) match against a fixed phrase list
rather than a substring search, so a real suspicious message that happens to
open with "Здравствуйте" or "Salom" is never misclassified: those carry other
content and will not equal a short phrase after normalization.
"""

import re

_LEADING_ADDRESS_RE = re.compile(r"^(avvalo|аввало)[,:\s]+")
_TRAILING_PUNCT_RE = re.compile(r"[?!.,;:…\s]+$")
_WHITESPACE_RE = re.compile(r"\s+")

_META_PHRASES = frozenset(
    {
        # Russian: greetings, capability/identity questions, thanks, test pings.
        "привет",
        "приветик",
        "здравствуй",
        "здравствуйте",
        "хай",
        "хеллоу",
        "алло",
        "что ты умеешь",
        "что вы умеете",
        "что ты можешь",
        "что вы можете",
        "что ты умеешь делать",
        "что ты можешь делать",
        "чем ты можешь помочь",
        "чем поможешь",
        "чем можешь помочь",
        "как ты работаешь",
        "как это работает",
        "как ты помогаешь",
        "что это",
        "что это такое",
        "что за бот",
        "кто ты",
        "кто вы",
        "ты кто",
        "вы кто",
        "help",
        "помощь",
        "справка",
        "спасибо",
        "спасибо большое",
        "благодарю",
        "ок",
        "окей",
        "test",
        "тест",
        "проверка связи",
        # Uzbek Latin: greetings, capability/identity questions, thanks, test pings.
        "salom",
        "assalomu alaykum",
        "alaykum assalom",
        "sen kimsan",
        "siz kimsiz",
        "sen nima qila olasan",
        "siz nima qila olasiz",
        "nima qila olasan",
        "nima qila olasiz",
        "nimalar qila olasan",
        "sen nima qilasan",
        "siz nima qilasiz",
        "nima ish qilasan",
        "qanday yordam bera olasan",
        "qanday ishlaydi",
        "bu nima",
        "bu qanday ishlaydi",
        "sen nima uchun kerak",
        "yordam",
        "rahmat",
        "katta rahmat",
        "tashakkur",
        "xop",
        "sinov",
        # Uzbek Cyrillic input, still expected to be read (see app.engine.language).
        "салом",
        "сен кимсан",
        "нима қила оласан",
        "раҳмат",
    }
)


def is_meta_message(text: str) -> bool:
    """Return True when *text* is chatter about the bot rather than a situation."""

    return _normalize(text) in _META_PHRASES


def _normalize(text: str) -> str:
    lowered = text.strip().casefold()
    lowered = _LEADING_ADDRESS_RE.sub("", lowered)
    lowered = _TRAILING_PUNCT_RE.sub("", lowered)
    return _WHITESPACE_RE.sub(" ", lowered).strip()
