"""Deterministic rule matching and structural signal extraction."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlparse

from app.engine.rules.loader import RuleDefinition, load_rule_pack
from app.engine.types import RuleHit, Signal

_APOSTROPHES = str.maketrans(
    {
        "\u2019": "'",
        "\u2018": "'",
        "`": "'",
        "\u02bc": "'",
        "\u055a": "'",
        "\u00b4": "'",
    }
)

_URL_RE = re.compile(
    r"(?ix)"
    r"\b(?:https?|hxxps?)://[^\s<>()]+"
    r"|\b(?:www\.)?[a-z0-9][a-z0-9.-]*(?:\.|\[\.\]|\(\.\))[a-z]{2,}"
    r"(?:/[^\s<>()]*)?"
)
_EMAIL_RE = re.compile(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b")
_HANDLE_RE = re.compile(r"(?<!\w)@[a-z0-9_]{4,32}\b", re.IGNORECASE)
# Match explicit international numbers first, then common Uzbek local/mobile
# formatting. Requiring ``+`` on the generic branch avoids classifying dates
# and spaced monetary amounts as phone signals.
_PHONE_RE = re.compile(
    r"(?<!\d)(?:"
    r"\+\d{1,3}(?:[\s().-]*\d){6,14}"
    r"|(?:\+?998[\s().-]?)?(?:\(?[2-9]\d\)?[\s().-]?)\d{3}"
    r"[\s().-]?\d{2}[\s().-]?\d{2}"
    r")(?!\d)"
)
_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
_CODE_RE = re.compile(
    r"(?iu)\b(?:sms\s*)?(?:otp|kod|code|код|парол|password)"
    r"[^\d]{0,20}(\d{4,8})(?!\d)"
)
_TRANSFER_NEAR_CARD_RE = re.compile(
    r"(?iu)(?:karta|карта|card|перевод|perevod|o'tkaz|ўтказ|tashla|ташла|"
    r"qaytar|қайтар).{0,80}(?:\d[ -]?){13,19}|(?:\d[ -]?){13,19}.{0,80}"
    r"(?:karta|карта|card|перевод|perevod|o'tkaz|ўтказ|tashla|ташла|qaytar|қайтар)"
)

_SHORTENER_DOMAINS = {
    "bit.ly",
    "cutt.ly",
    "goo.gl",
    "is.gd",
    "lnkd.in",
    "ow.ly",
    "s.id",
    "shorturl.at",
    "t.co",
    "tiny.cc",
    "tinyurl.com",
    "clck.ru",
}
_BRAND_ALLOWED_DOMAINS: dict[str, tuple[str, ...]] = {
    "agrobank": ("agrobank.uz",),
    "anorbank": ("anorbank.uz",),
    "beeline": ("beeline.uz",),
    "click": ("click.uz",),
    "hamkorbank": ("hamkorbank.uz",),
    "humo": ("humocard.uz", "humo.uz"),
    "ipoteka": ("ipotekabank.uz",),
    "kapitalbank": ("kapitalbank.uz",),
    "olx": ("olx.uz",),
    "payme": ("payme.uz",),
    "telegram": ("telegram.org", "t.me"),
    "uzcard": ("uzcard.uz",),
    "uzum": ("uzum.uz", "uzumbank.uz"),
    "xalqqbank": ("xb.uz",),
}


def run_rules(text: str, face_id: str) -> tuple[list[RuleHit], list[Signal]]:
    """Run a face's keyword rules and structural extractors over raw local text."""

    pack = load_rule_pack(face_id)
    normalized = normalize_text(text)
    hits_by_id: dict[str, RuleHit] = {}
    signals: list[Signal] = []
    signal_keys: set[tuple[str, str | None]] = set()

    for rule in pack.rules:
        if _rule_matches(rule, normalized):
            hits_by_id[rule.id] = RuleHit(
                rule_id=rule.id,
                family=rule.family,
                message_key=rule.message_key,
                severity=rule.severity,
            )
            if rule.emits_signal:
                _add_signal(signals, signal_keys, kind=rule.emits_signal, note=rule.family)

    for signal in extract_structural_signals(text):
        _add_signal(signals, signal_keys, kind=signal.kind, note=signal.note)

    return list(hits_by_id.values()), signals


def extract_structural_signals(text: str) -> list[Signal]:
    """Extract privacy-safe structural facts such as link/card/phone presence."""

    signals: list[Signal] = []
    signal_keys: set[tuple[str, str | None]] = set()
    text_without_emails = _EMAIL_RE.sub(" ", text)

    for match in _URL_RE.finditer(text_without_emails):
        label = classify_link(match.group(0))
        if label == "shortened":
            _add_signal(signals, signal_keys, kind="link_shortened", note=label)
        elif label == "lookalike-domain":
            _add_signal(signals, signal_keys, kind="link_lookalike", note=label)
        else:
            _add_signal(signals, signal_keys, kind="link", note=None)

    if _EMAIL_RE.search(text):
        _add_signal(signals, signal_keys, kind="email", note=None)
    if _HANDLE_RE.search(text):
        _add_signal(signals, signal_keys, kind="handle", note=None)
    if _PHONE_RE.search(text):
        _add_signal(signals, signal_keys, kind="phone", note=None)
    if _CODE_RE.search(text):
        _add_signal(signals, signal_keys, kind="code", note=None)
    if any(_card_digits(match.group(0)) for match in _CARD_RE.finditer(text)):
        _add_signal(signals, signal_keys, kind="card", note=None)
    if _TRANSFER_NEAR_CARD_RE.search(normalize_text(text)):
        _add_signal(signals, signal_keys, kind="card_personal", note="transfer-to-card phrasing")

    return signals


def normalize_text(text: str) -> str:
    """Lowercase and normalize punctuation variants without changing meaning."""

    normalized = unicodedata.normalize("NFKC", text).translate(_APOSTROPHES)
    normalized = normalized.replace("\u0451", "\u0435").replace("\u0401", "\u0435")
    return re.sub(r"\s+", " ", normalized.casefold()).strip()


def classify_link(raw_url: str) -> str | None:
    """Classify a raw link into the safe labels used by minimization."""

    domain = _domain_from_url(raw_url)
    if not domain:
        return None

    if domain in _SHORTENER_DOMAINS:
        return "shortened"

    domain_labels = re.split(r"[^a-z0-9]+", domain)
    for brand, allowed_domains in _BRAND_ALLOWED_DOMAINS.items():
        if _domain_is_allowed(domain, allowed_domains):
            continue
        if brand in domain or any(_looks_like_brand(label, brand) for label in domain_labels):
            return "lookalike-domain"

    return None


def _rule_matches(rule: RuleDefinition, normalized_text: str) -> bool:
    for patterns in rule.match.values():
        for pattern in patterns:
            normalized_pattern = normalize_text(pattern)
            if normalized_pattern.startswith("regex:"):
                if re.search(normalized_pattern.removeprefix("regex:"), normalized_text):
                    return True
            elif normalized_pattern in normalized_text:
                return True
    return False


def _domain_from_url(raw_url: str) -> str | None:
    cleaned = raw_url.strip().strip(".,;:!?)]}\"'")
    cleaned = cleaned.replace("[.]", ".").replace("(.)", ".")
    cleaned = re.sub(r"(?i)^hxxp", "http", cleaned)
    if "://" not in cleaned:
        cleaned = f"https://{cleaned}"

    parsed = urlparse(cleaned)
    domain = (parsed.hostname or "").casefold().strip(".")
    if domain.startswith("www."):
        domain = domain.removeprefix("www.")
    return domain or None


def _domain_is_allowed(domain: str, allowed_domains: tuple[str, ...]) -> bool:
    return any(domain == allowed or domain.endswith(f".{allowed}") for allowed in allowed_domains)


def _looks_like_brand(label: str, brand: str) -> bool:
    if len(brand) < 4 or abs(len(label) - len(brand)) > 2:
        return False
    if label == brand:
        return True
    return _levenshtein_at_most_one(label, brand)


def _levenshtein_at_most_one(left: str, right: str) -> bool:
    if left == right:
        return True
    if abs(len(left) - len(right)) > 1:
        return False

    edits = 0
    i = 0
    j = 0
    while i < len(left) and j < len(right):
        if left[i] == right[j]:
            i += 1
            j += 1
            continue
        edits += 1
        if edits > 1:
            return False
        if len(left) == len(right):
            i += 1
            j += 1
        elif len(left) > len(right):
            i += 1
        else:
            j += 1

    return True


def _card_digits(value: str) -> str | None:
    digits = re.sub(r"\D", "", value)
    if 13 <= len(digits) <= 19:
        return digits
    return None


def _add_signal(
    signals: list[Signal],
    signal_keys: set[tuple[str, str | None]],
    *,
    kind: str,
    note: str | None,
) -> None:
    key = (kind, note)
    if key not in signal_keys:
        signal_keys.add(key)
        signals.append(Signal(kind=kind, note=note))
