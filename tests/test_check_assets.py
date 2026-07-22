"""Contract tests for the single check surface and the assets it loads.

Avvalo has one consumer checker, so there is no product-face registry to pin.
What still needs pinning is that the engine's on-disk assets — the rule pack and
the prompt templates — exist and are non-empty, so a rename or a bad move can't
silently ship a checker with no rules.
"""

from app.config import Settings
from app.engine.llm.prompt import _CHECK_PROMPT, _SYSTEM_PROMPT
from app.engine.rules import load_rule_pack
from app.engine.rules.loader import RULE_PACK_DIR


def test_rule_pack_directory_exists_and_has_yaml() -> None:
    assert RULE_PACK_DIR.is_dir(), f"rule pack directory missing: {RULE_PACK_DIR}"
    assert list(RULE_PACK_DIR.glob("*.yaml")), f"no YAML rules in {RULE_PACK_DIR}"


def test_rule_pack_does_not_sweep_in_the_shared_feed_directory() -> None:
    """rules/shared/ holds URL-reputation feed data, not checker rules."""

    rule_ids = {rule.id for rule in load_rule_pack().rules}
    assert rule_ids, "rule pack loaded no rules"
    assert not any(rule_id.startswith("shared.") for rule_id in rule_ids)


def test_prompt_templates_exist_and_are_not_empty() -> None:
    for template in (_SYSTEM_PROMPT, _CHECK_PROMPT):
        assert template.is_file(), f"prompt template missing: {template}"
        assert template.read_text(encoding="utf-8").strip(), f"empty prompt: {template}"


def test_daily_check_limit_default_matches_the_spec() -> None:
    assert Settings.model_fields["daily_check_limit"].default == 5
