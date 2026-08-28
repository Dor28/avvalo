"""YAML rule-pack loader for deterministic local checks."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
# Top-level YAML only: rules/shared/ holds feed data for the URL-reputation job,
# not checker rules, so it must not be swept into the pack.
RULE_PACK_DIR = _REPO_ROOT / "rules"

# How a literal pattern is anchored against normalized text (PIPELINE_V2 §6).
# ``substring`` is the historical behavior and stays the default: every rule and
# every stored override written before this field existed keeps matching exactly
# as it did. ``word_prefix`` anchors to a word start, which is what Uzbek
# agglutination needs ("kod" then covers "kodni"/"kodingizni" without listing
# them). The ``regex:`` pattern prefix is unaffected by either mode.
MATCH_MODE_SUBSTRING = "substring"
MATCH_MODE_WORD_PREFIX = "word_prefix"
MATCH_MODES = (MATCH_MODE_SUBSTRING, MATCH_MODE_WORD_PREFIX)

_REQUIRES_KEYS = ("any_of", "all_of", "signals")

# The merged YAML+database pack currently in force. A one-slot list rather than
# a module global so ``set_active_rule_pack`` can rebind it without ``global``.
# ``None`` until the first refresh succeeds; see ``load_rule_pack``.
_ACTIVE_PACK: list[RulePack | None] = [None]


@dataclass(frozen=True)
class RuleRequirement:
    """Co-occurrence gate on a rule (PIPELINE_V2 §6).

    A rule carrying one fires only when the surrounding evidence also fired:
    at least one of ``any_of``, every one of ``all_of``, and every signal kind
    in ``signals``. An empty tuple means "no constraint from this clause".

    A referenced rule ID that no pack rule defines is simply never satisfied —
    a dangling reference must not fail the pack, because disabling one rule
    through an override would otherwise take the whole pack down.
    """

    any_of: tuple[str, ...] = ()
    all_of: tuple[str, ...] = ()
    signals: tuple[str, ...] = ()

    @property
    def rule_ids(self) -> tuple[str, ...]:
        """Every rule ID this gate references, in either clause."""

        return (*self.any_of, *self.all_of)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any] | None) -> RuleRequirement | None:
        """Project an already-validated mapping onto the frozen contract."""

        if not raw:
            return None
        return cls(
            any_of=tuple(raw.get("any_of") or ()),
            all_of=tuple(raw.get("all_of") or ()),
            signals=tuple(raw.get("signals") or ()),
        )


@dataclass(frozen=True)
class RuleDefinition:
    """One validated rule flattened from the YAML pack.

    ``family`` is the scam-family taxonomy the rule belongs to (credential_theft,
    urgency_secrecy, …) — it has nothing to do with any product identifier.

    ``exclude``, ``match_mode``, and ``requires`` are the optional precision
    controls from PIPELINE_V2 §6. A rule that sets none of them behaves exactly
    as it did before they existed.
    """

    id: str
    family: str
    desc: str
    message_key: str
    severity: int
    match: dict[str, tuple[str, ...]]
    emits_signal: str | None = None
    # Same per-script shape as ``match``: any hit here suppresses the rule.
    exclude: dict[str, tuple[str, ...]] = field(default_factory=dict)
    match_mode: str = MATCH_MODE_SUBSTRING
    requires: RuleRequirement | None = None


@dataclass(frozen=True)
class RulePack:
    """The validated deterministic rule pack."""

    rules: tuple[RuleDefinition, ...]
    descriptions: dict[str, str]

    def __post_init__(self) -> None:
        validate_requires_graph(self.rules)


def validate_requires_graph(rules: tuple[RuleDefinition, ...]) -> None:
    """Reject a pack whose ``requires`` gates reference gated rules.

    PIPELINE_V2 §6: a rule carrying ``requires`` may only reference rules that
    do not themselves carry ``requires``. That keeps evaluation to one
    deterministic pass with no fixpoint iteration and no ordering dependence.
    A violation raises, which fails the pack the same way a duplicate rule ID
    or a malformed ``match`` block does — the caller degrades to the pack
    already in force, and a fresh process to the shipped YAML baseline.
    """

    gated = {rule.id for rule in rules if rule.requires is not None}
    if not gated:
        return
    for rule in rules:
        if rule.requires is None:
            continue
        conflicts = sorted(set(rule.requires.rule_ids) & gated)
        if conflicts:
            raise ValueError(
                f"Rule {rule.id!r} requires rule(s) that themselves carry 'requires': "
                f"{conflicts}"
            )


def load_rule_pack() -> RulePack:
    """Return the rule pack in force.

    Synchronous by design: the pack is read several times per check and from
    inside the formatter and prompt builder, so it is served from a process-level
    snapshot rather than queried. ``app.rules_store.apply`` swaps that snapshot
    in on a schedule and after an operator edit. Before the first successful
    refresh — and whenever the database is unreachable — this falls back to the
    YAML pack shipped in the image, so detection degrades to the baseline
    instead of to nothing.
    """

    return _ACTIVE_PACK[0] or load_yaml_rule_pack()


def set_active_rule_pack(pack: RulePack) -> None:
    """Publish a merged pack as the one in force."""

    _ACTIVE_PACK[0] = pack


def clear_active_rule_pack() -> None:
    """Drop the merged pack, reverting to the shipped YAML baseline."""

    _ACTIVE_PACK[0] = None


@cache
def load_yaml_rule_pack() -> RulePack:
    """Load and validate every YAML rule file in the shipped rule pack."""

    pack_dir = RULE_PACK_DIR
    if not pack_dir.exists() or not pack_dir.is_dir():
        raise FileNotFoundError(f"Rule pack directory does not exist: {pack_dir}")

    rule_ids: set[str] = set()
    rules: list[RuleDefinition] = []
    for path in sorted([*pack_dir.glob("*.yaml"), *pack_dir.glob("*.yml")]):
        rules.extend(_load_rule_file(path, rule_ids))

    return RulePack(
        rules=tuple(rules),
        descriptions={rule.id: rule.desc for rule in rules},
    )


def _load_rule_file(path: Path, seen_rule_ids: set[str]) -> list[RuleDefinition]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    families = _require_list(data, "families", source=path)
    rules: list[RuleDefinition] = []
    for index, family_data in enumerate(families):
        family_source = f"{path}:families[{index}]"
        family = _require_str(family_data, "family", source=family_source)
        family_rules = _require_list(family_data, "rules", source=family_source)
        for rule_index, rule_data in enumerate(family_rules):
            source = f"{family_source}.rules[{rule_index}]"
            rule = _parse_rule(rule_data, family=family, source=source)
            if rule.id in seen_rule_ids:
                raise ValueError(f"Duplicate rule id {rule.id!r} in {source}")
            seen_rule_ids.add(rule.id)
            rules.append(rule)

    return rules


def _parse_rule(data: Any, *, family: str, source: str) -> RuleDefinition:
    if not isinstance(data, dict):
        raise ValueError(f"{source} must be a mapping")

    match = _require_dict(data, "match", source=source)
    return RuleDefinition(
        id=_require_str(data, "id", source=source),
        family=family,
        desc=_require_str(data, "desc", source=source),
        message_key=_require_str(data, "message_key", source=source),
        severity=_require_int(data, "severity", source=source),
        match=_parse_match(match, source=f"{source}.match"),
        emits_signal=_optional_str(data, "emits_signal", source=source),
        exclude=_parse_exclude(data, source=source),
        match_mode=_parse_match_mode(data, source=source),
        requires=_parse_requires(data, source=source),
    )


def _parse_match(data: dict[str, Any], *, source: str) -> dict[str, tuple[str, ...]]:
    parsed = _parse_pattern_groups(data, source=source)
    if not any(parsed.values()):
        raise ValueError(f"{source} must contain at least one non-empty pattern")
    return parsed


def _parse_pattern_groups(data: dict[str, Any], *, source: str) -> dict[str, tuple[str, ...]]:
    parsed: dict[str, tuple[str, ...]] = {}
    for language, patterns in data.items():
        if not isinstance(language, str):
            raise ValueError(f"{source} keys must be strings")
        if not isinstance(patterns, list) or not all(isinstance(item, str) for item in patterns):
            raise ValueError(f"{source}.{language} must be a list of strings")
        parsed[language] = tuple(pattern for pattern in patterns if pattern.strip())
    return parsed


def _parse_exclude(data: dict[str, Any], *, source: str) -> dict[str, tuple[str, ...]]:
    value = data.get("exclude")
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{source}.exclude must be a mapping")
    parsed = _parse_pattern_groups(value, source=f"{source}.exclude")
    if not any(parsed.values()):
        # An empty exclude block is an authoring slip, not an intent: it would
        # read as "this false positive is handled" while suppressing nothing.
        raise ValueError(f"{source}.exclude must contain at least one non-empty pattern when set")
    return parsed


def _parse_match_mode(data: dict[str, Any], *, source: str) -> str:
    value = data.get("match_mode")
    if value is None:
        return MATCH_MODE_SUBSTRING
    if value not in MATCH_MODES:
        raise ValueError(f"{source}.match_mode must be one of {list(MATCH_MODES)}")
    return value


def _parse_requires(data: dict[str, Any], *, source: str) -> RuleRequirement | None:
    value = data.get("requires")
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{source}.requires must be a mapping")

    parsed: dict[str, tuple[str, ...]] = {}
    for key, entries in value.items():
        if key not in _REQUIRES_KEYS:
            raise ValueError(f"{source}.requires keys must be one of {list(_REQUIRES_KEYS)}")
        if not isinstance(entries, list) or not all(isinstance(item, str) for item in entries):
            raise ValueError(f"{source}.requires.{key} must be a list of strings")
        parsed[key] = tuple(entry.strip() for entry in entries if entry.strip())

    if not any(parsed.values()):
        raise ValueError(f"{source}.requires must constrain at least one rule id or signal")
    return RuleRequirement.from_mapping(parsed)


def _require_dict(data: Any, key: str, *, source: object) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError(f"{source} must be a mapping")
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{source}.{key} must be a mapping")
    return value


def _require_list(data: Any, key: str, *, source: object) -> list[Any]:
    if not isinstance(data, dict):
        raise ValueError(f"{source} must be a mapping")
    value = data.get(key)
    if not isinstance(value, list):
        raise ValueError(f"{source}.{key} must be a list")
    return value


def _require_str(data: Any, key: str, *, source: object) -> str:
    if not isinstance(data, dict):
        raise ValueError(f"{source} must be a mapping")
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{source}.{key} must be a non-empty string")
    return value


def _optional_str(data: dict[str, Any], key: str, *, source: object) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{source}.{key} must be a non-empty string when set")
    return value


def _require_int(data: Any, key: str, *, source: object) -> int:
    if not isinstance(data, dict):
        raise ValueError(f"{source} must be a mapping")
    value = data.get(key)
    if not isinstance(value, int):
        raise ValueError(f"{source}.{key} must be an integer")
    return value
