"""Single active product-face registry contract tests.

A face selects a rule pack + prompt template + daily limit and nothing else.
These tests pin the registry to the plan and verify it points at assets that
actually exist on disk, so faces.py can't drift away from the rule packs and
prompts the pipeline loads.
"""

from pathlib import Path

from app.config import Settings
from app.engine.faces import FACES, Face

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_exactly_the_one_active_face() -> None:
    assert set(FACES) == {"family"}
    for key, face in FACES.items():
        assert isinstance(face, Face)
        assert face.id == key, f"FACES['{key}'].id must equal its key"


def test_daily_limits_match_the_spec_and_config_defaults() -> None:
    assert FACES["family"].daily_limit == 5

    # The registry must not disagree with the configurable defaults in config.py.
    assert FACES["family"].daily_limit == Settings.model_fields[
        "daily_limit_family"
    ].default


def test_each_face_points_at_an_existing_rule_pack() -> None:
    for face in FACES.values():
        pack_dir = REPO_ROOT / face.rule_pack_dir
        assert pack_dir.is_dir(), f"{face.id}: rule_pack_dir '{face.rule_pack_dir}' missing"
        assert list(pack_dir.glob("*.yaml")), f"{face.id}: no YAML rules in {face.rule_pack_dir}"


def test_each_face_points_at_an_existing_prompt_template() -> None:
    for face in FACES.values():
        template = REPO_ROOT / face.prompt_template
        assert template.is_file(), f"{face.id}: prompt_template '{face.prompt_template}' missing"
        assert template.read_text(encoding="utf-8").strip(), f"{face.id}: prompt template is empty"
