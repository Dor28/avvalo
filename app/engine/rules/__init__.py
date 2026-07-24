"""Deterministic rule engine package."""

from app.engine.rules.engine import (
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

# Re-exported: link classification moved to the shared analyzer, but callers
# reach it through the rules package.
from app.engine.url import classify_link

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
