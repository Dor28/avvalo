"""Prompt-asset tests (V1_TECHNICAL_PLAN §8, §9).

The prompts are pre-authored safety-critical assets (§0.6). prompt.py (T6) will
fill the face templates; until then these tests check the assets exist, expose
the placeholders the builder fills, and still carry the non-negotiable safety
contract — so an accidental edit that strips a constraint is caught.
"""

from pathlib import Path

import pytest

from app.engine.faces import FACES
from app.engine.types import DraftOutput

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPTS = REPO_ROOT / "prompts"

FACE_TEMPLATE_PLACEHOLDERS = ("{language}", "{minimized_text}", "{rule_hits}", "{signals}")


def _read(name: str) -> str:
    path = PROMPTS / name
    assert path.is_file(), f"prompt '{name}' is missing"
    text = path.read_text(encoding="utf-8")
    assert text.strip(), f"prompt '{name}' is empty"
    return text


def test_required_prompt_files_exist() -> None:
    for name in ("system_safety.txt", "family.txt", "merchants.txt"):
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


@pytest.mark.parametrize("name", ["family.txt", "merchants.txt"])
def test_face_templates_expose_builder_placeholders(name: str) -> None:
    template = _read(name)
    for placeholder in FACE_TEMPLATE_PLACEHOLDERS:
        assert placeholder in template, f"{name}: missing placeholder {placeholder}"


def test_merchants_prompt_forbids_claiming_money_arrived() -> None:
    # §8: "(merchants) NEVER state that money arrived/was received".
    assert "money has arrived" in _read("merchants.txt").lower()


def test_faces_reference_prompt_files_that_exist() -> None:
    for face in FACES.values():
        assert (REPO_ROOT / face.prompt_template).is_file(), (
            f"{face.id}: prompt_template '{face.prompt_template}' does not exist"
        )
