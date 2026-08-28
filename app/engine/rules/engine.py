"""Deterministic rule matching and structural signal extraction."""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from app.engine.rules.loader import (
    MATCH_MODE_SUBSTRING,
    MATCH_MODE_WORD_PREFIX,
    RuleDefinition,
    RulePack,
    RuleRequirement,
    load_rule_pack,
)
from app.engine.types import RuleHit, Signal
from app.engine.url import (
    LABEL_CREDENTIALS,
    LABEL_DOMAIN_IN_SUBDOMAIN,
    LABEL_IP,
    LABEL_LOOKALIKE,
    LABEL_MIXED_SCRIPT,
    LABEL_SHORTENED,
    URL_RE,
    classify_link,
)

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

# Every link-shape label maps to the signal kind for its class of deception, so
# knowledge cards keep triggering on `link_lookalike` as new shapes are detected.
_SIGNAL_KIND_BY_LABEL = {
    LABEL_SHORTENED: "link_shortened",
    LABEL_LOOKALIKE: "link_lookalike",
    LABEL_DOMAIN_IN_SUBDOMAIN: "link_lookalike",
    LABEL_MIXED_SCRIPT: "link_lookalike",
    LABEL_CREDENTIALS: "link_userinfo",
    LABEL_IP: "link_ip",
}


def run_rules(text: str) -> tuple[list[RuleHit], list[Signal]]:
    """Run the keyword rules and structural extractors over raw local text.

    Two passes, never more (PIPELINE_V2 §6). The base pass matches every rule
    that carries no ``requires`` gate and collects the structural signals; the
    second pass admits the gated rules whose co-occurrence conditions the base
    result already satisfies. Because a gate may only reference ungated rules
    (enforced when the pack loads), one pass is enough and the outcome does not
    depend on rule order. A signal emitted by a gated rule therefore lands in
    the result but never feeds another gate.
    """

    pack = load_rule_pack()
    normalized = normalize_text(text)
    hits_by_id, signals, signal_keys = _base_pass(pack, text, normalized)

    gated = [rule for rule in pack.rules if rule.requires is not None]
    if gated:
        fired_rule_ids = frozenset(hits_by_id)
        signal_kinds = frozenset(signal.kind for signal in signals)
        for rule in gated:
            if not _requirements_met(rule.requires, fired_rule_ids, signal_kinds):
                continue
            if _rule_matches(rule, normalized):
                _record_hit(rule, hits_by_id, signals, signal_keys)

    return list(hits_by_id.values()), signals


def _base_pass(
    pack: RulePack,
    text: str,
    normalized_text: str,
    *,
    ignore_rule_id: str | None = None,
) -> tuple[dict[str, RuleHit], list[Signal], set[tuple[str, str | None]]]:
    """Match every ungated rule and extract the structural signals.

    ``ignore_rule_id`` drops one rule from the pass so the operator dry-run can
    evaluate a draft's gate without the stored version of that same rule
    standing in for it.
    """

    hits_by_id: dict[str, RuleHit] = {}
    signals: list[Signal] = []
    signal_keys: set[tuple[str, str | None]] = set()

    for rule in pack.rules:
        if rule.requires is not None or rule.id == ignore_rule_id:
            continue
        if _rule_matches(rule, normalized_text):
            _record_hit(rule, hits_by_id, signals, signal_keys)

    for signal in extract_structural_signals(text):
        _add_signal(signals, signal_keys, kind=signal.kind, note=signal.note)

    return hits_by_id, signals, signal_keys


def _record_hit(
    rule: RuleDefinition,
    hits_by_id: dict[str, RuleHit],
    signals: list[Signal],
    signal_keys: set[tuple[str, str | None]],
) -> None:
    hits_by_id[rule.id] = RuleHit(
        rule_id=rule.id,
        family=rule.family,
        message_key=rule.message_key,
        severity=rule.severity,
    )
    if rule.emits_signal:
        _add_signal(signals, signal_keys, kind=rule.emits_signal, note=rule.family)


def _requirements_met(
    requires: RuleRequirement,
    fired_rule_ids: frozenset[str],
    signal_kinds: frozenset[str],
) -> bool:
    """Whether the base pass satisfies a rule's co-occurrence gate."""

    if requires.any_of and fired_rule_ids.isdisjoint(requires.any_of):
        return False
    if not fired_rule_ids.issuperset(requires.all_of):
        return False
    return signal_kinds.issuperset(requires.signals)


def extract_structural_signals(text: str) -> list[Signal]:
    """Extract privacy-safe structural facts such as link/card/phone presence."""

    signals: list[Signal] = []
    signal_keys: set[tuple[str, str | None]] = set()
    text_without_emails = _EMAIL_RE.sub(" ", text)

    for match in URL_RE.finditer(text_without_emails):
        label = classify_link(match.group(0))
        kind = _SIGNAL_KIND_BY_LABEL.get(label) if label else None
        if kind is None:
            _add_signal(signals, signal_keys, kind="link", note=None)
        else:
            _add_signal(signals, signal_keys, kind=kind, note=label)

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


def matching_patterns(rule: RuleDefinition, text: str) -> tuple[str, ...]:
    """Return every pattern in ``rule`` that matches ``text``.

    Shared with the operator dry-run so a preview can never disagree with what
    production matching actually does. That includes the suppressions: an
    ``exclude`` hit or an unmet ``requires`` gate means the rule would not fire,
    so nothing is reported even when individual keywords are present.
    """

    normalized_text = normalize_text(text)
    if not _rule_matches(rule, normalized_text):
        return ()
    if not _gate_open(rule, text, normalized_text):
        return ()
    return tuple(
        pattern
        for patterns in rule.match.values()
        for pattern in patterns
        if _pattern_matches(normalize_text(pattern), normalized_text, rule.match_mode)
    )


def _gate_open(rule: RuleDefinition, text: str, normalized_text: str) -> bool:
    """Whether ``rule``'s ``requires`` gate would be satisfied for ``text``.

    Only the dry-run needs this: ``run_rules`` already holds the base result the
    gate is evaluated against. The pack in force supplies that context here, with
    the previewed rule itself left out so a stored earlier version of it cannot
    satisfy its own gate.
    """

    if rule.requires is None:
        return True
    hits_by_id, signals, _keys = _base_pass(
        load_rule_pack(), text, normalized_text, ignore_rule_id=rule.id
    )
    return _requirements_met(
        rule.requires,
        frozenset(hits_by_id),
        frozenset(signal.kind for signal in signals),
    )


def _pattern_matches(
    normalized_pattern: str,
    normalized_text: str,
    match_mode: str = MATCH_MODE_SUBSTRING,
) -> bool:
    if normalized_pattern.startswith("regex:"):
        try:
            return bool(re.search(normalized_pattern.removeprefix("regex:"), normalized_text))
        except re.error:
            # Patterns are validated on write, but a row written out of band
            # must degrade to "no match" rather than break every check.
            return False
    if match_mode == MATCH_MODE_WORD_PREFIX:
        return bool(_word_prefix_matcher(normalized_pattern).search(normalized_text))
    return normalized_pattern in normalized_text


@lru_cache(maxsize=2048)
def _word_prefix_matcher(literal: str) -> re.Pattern[str]:
    r"""Compile a word-start anchored matcher for one normalized literal.

    ``(?<!\w)`` plus the escaped literal, so "kod" covers "kodni" and
    "kodingizni" but not "bikod". Cached because rule literals are a bounded set
    of reviewed reference data — submitted content is only ever the subject of a
    match, never a cache key.
    """

    return re.compile(rf"(?<!\w){re.escape(literal)}")


def _rule_matches(rule: RuleDefinition, normalized_text: str) -> bool:
    """Whether ``rule`` fires, exclusions applied, gate not considered.

    An ``exclude`` hit wins over everything the ``match`` groups found: it is
    how a reviewer kills one false positive without weakening the keyword that
    catches the true hits.
    """

    if _any_pattern_matches(rule.exclude, rule.match_mode, normalized_text):
        return False
    return _any_pattern_matches(rule.match, rule.match_mode, normalized_text)


def _any_pattern_matches(
    groups: dict[str, tuple[str, ...]],
    match_mode: str,
    normalized_text: str,
) -> bool:
    return any(
        _pattern_matches(normalize_text(pattern), normalized_text, match_mode)
        for patterns in groups.values()
        for pattern in patterns
    )


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
