"""Safety-critical prompt-asset and template-contract tests.

The prompt builder fills the single checker template at runtime. These tests pin
its placeholders and non-negotiable safety constraints so an accidental asset
edit cannot silently remove them.
"""

from pathlib import Path

import pytest

from app.engine.llm.prompt import _CHECK_PROMPT, _SYSTEM_PROMPT
from app.engine.types import DraftOutput

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPTS = REPO_ROOT / "prompts"

CHECK_TEMPLATE_PLACEHOLDERS = (
    "{language}",
    "{minimized_text}",
    "{rule_hits}",
    "{signals}",
    "{knowledge}",
)


def _read(name: str) -> str:
    path = PROMPTS / name
    assert path.is_file(), f"prompt '{name}' is missing"
    text = path.read_text(encoding="utf-8")
    assert text.strip(), f"prompt '{name}' is empty"
    return text


def test_required_prompt_files_exist() -> None:
    for name in ("system_safety.txt", "check.txt"):
        _read(name)


def test_system_prompt_declares_the_draft_output_schema() -> None:
    """The JSON keys the system prompt asks for must match the DraftOutput contract (§6)."""
    system = _read("system_safety.txt")
    for field in DraftOutput.model_fields:
        assert f'"{field}"' in system, f"system prompt must declare JSON key '{field}'"


def test_system_prompt_keeps_the_core_prohibitions() -> None:
    system = _read("system_safety.txt").lower()
    # §8/§9: no verdicts, no claimed identity/database checks, ground every flag.
    for token in ("safe", "scammer", "fraud", "json"):
        assert token in system, f"system prompt should reference '{token}' (§8 constraints)"


@pytest.mark.parametrize("name", ["check.txt"])
def test_check_template_exposes_builder_placeholders(name: str) -> None:
    template = _read(name)
    for placeholder in CHECK_TEMPLATE_PLACEHOLDERS:
        assert placeholder in template, f"{name}: missing placeholder {placeholder}"


def test_consumer_prompt_forbids_confirming_payment_from_a_screenshot() -> None:
    prompt = _read("check.txt").lower()
    assert "incoming payment arrived" in prompt
    assert "screenshot" in prompt


def test_engine_references_prompt_files_that_exist() -> None:
    for template in (_SYSTEM_PROMPT, _CHECK_PROMPT):
        assert template.is_file(), f"prompt template does not exist: {template}"
