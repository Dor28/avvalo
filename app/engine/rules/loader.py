"""YAML rule-pack loader for deterministic local checks."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
# Top-level YAML only: rules/shared/ holds feed data for the URL-reputation job,
# not checker rules, so it must not be swept into the pack.
RULE_PACK_DIR = _REPO_ROOT / "rules"


@dataclass(frozen=True)
class RuleDefinition:
    """One validated rule flattened from the YAML pack.

    ``family`` is the scam-family taxonomy the rule belongs to (credential_theft,
    urgency_secrecy, …) — it has nothing to do with any product identifier.
    """

    id: str
    family: str
    desc: str
    message_key: str
    severity: int
    match: dict[str, tuple[str, ...]]
    emits_signal: str | None = None


@dataclass(frozen=True)
class RulePack:
    """The validated deterministic rule pack."""

    rules: tuple[RuleDefinition, ...]
    descriptions: dict[str, str]


@cache
def load_rule_pack() -> RulePack:
    """Load and validate every YAML rule file in the rule pack."""

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
    )


def _parse_match(data: dict[str, Any], *, source: str) -> dict[str, tuple[str, ...]]:
    parsed: dict[str, tuple[str, ...]] = {}
    for language, patterns in data.items():
        if not isinstance(language, str):
            raise ValueError(f"{source} keys must be strings")
        if not isinstance(patterns, list) or not all(isinstance(item, str) for item in patterns):
            raise ValueError(f"{source}.{language} must be a list of strings")
        parsed[language] = tuple(pattern for pattern in patterns if pattern.strip())

    if not any(parsed.values()):
        raise ValueError(f"{source} must contain at least one non-empty pattern")
    return parsed


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
