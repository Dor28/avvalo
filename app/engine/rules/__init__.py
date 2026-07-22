"""Deterministic rule engine package."""

from app.engine.rules.engine import (
    classify_link,
    extract_structural_signals,
    matching_patterns,
    normalize_text,
    run_rules,
)
from app.engine.rules.loader import (
    RuleDefinition,
    RulePack,
    load_rule_pack,
    load_yaml_rule_pack,
)

__all__ = [
    "RuleDefinition",
    "RulePack",
    "classify_link",
    "extract_structural_signals",
    "load_rule_pack",
    "load_yaml_rule_pack",
    "matching_patterns",
    "normalize_text",
    "run_rules",
]
