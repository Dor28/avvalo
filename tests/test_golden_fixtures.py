"""Golden-fixture integrity tests (V1_TECHNICAL_PLAN §13 T5/T10, §8).

The golden fixtures are the mandatory acceptance set: 5 Family Shield + >=3
Seller Guard examples. End-to-end engine evaluation against them lands with the
LLM (T6/T7/T10); until then these tests validate the fixtures' own structure and
cross-check them against the rule packs so an example can't expect a family that
no rule pack models.
"""

import json
from pathlib import Path

import pytest
import yaml

from app.engine.faces import FACES
from app.engine.types import InputType, Language

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = REPO_ROOT / "tests" / "fixtures" / "golden"

REQUIRED_KEYS = {
    "id",
    "face",
    "language",
    "input_type",
    "input",
    "expected_rule_families",
    "must_include",
    "must_not_contain",
    "no_signal",
}

# §8: Seller Guard must never imply a payment was actually received. Each SG
# fixture must forbid at least one "money confirmed" phrasing. Apostrophes are
# normalized so curly/straight variants compare equal.
SG_MONEY_CONFIRMED = {
    "деньги пришли",
    "оплата прошла",
    "платёж настоящий",
    "pul keldi",
    "to'lov o'tdi",
    "пул тушди",
    "тўлов ўтди",
}


_CURLY_APOSTROPHES = (chr(0x2018), chr(0x2019))  # left/right single quotation marks


def _norm(text: str) -> str:
    # Normalize curly apostrophes to a straight quote so quote variants compare equal.
    for curly in _CURLY_APOSTROPHES:
        text = text.replace(curly, "'")
    return text.lower()


def _load(face: str) -> list[dict]:
    data = json.loads((GOLDEN_DIR / f"{face}.json").read_text(encoding="utf-8"))
    assert isinstance(data, list), f"{face}.json must be a JSON array"
    return data


def _families_for(face: str) -> set[str]:
    families: set[str] = set()
    for path in sorted((REPO_ROOT / FACES[face].rule_pack_dir).glob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        families.update(f["family"] for f in doc["families"])
    return families


def test_minimum_golden_counts() -> None:
    # §13: "5 FS + >=3 SG golden examples".
    assert len(_load("family_shield")) == 5
    assert len(_load("seller_guard")) >= 3


@pytest.mark.parametrize("face", ["family_shield", "seller_guard"])
def test_fixture_shape_and_values(face: str) -> None:
    valid_languages = {lang.value for lang in Language}
    valid_input_types = {it.value for it in InputType}
    seen_ids: set[str] = set()

    for fixture in _load(face):
        fid = fixture.get("id", "<no-id>")
        missing = REQUIRED_KEYS - fixture.keys()
        assert not missing, f"{fid}: missing keys {missing}"

        assert fixture["id"] not in seen_ids, f"duplicate fixture id {fixture['id']}"
        seen_ids.add(fixture["id"])

        assert fixture["face"] == face, f"{fid}: face '{fixture['face']}' wrong file"
        assert fixture["language"] in valid_languages, f"{fid}: bad language {fixture['language']}"
        assert fixture["input_type"] in valid_input_types, f"{fid}: bad input_type"
        assert isinstance(fixture["input"], str) and fixture["input"].strip(), f"{fid}: empty input"
        assert isinstance(fixture["no_signal"], bool), f"{fid}: no_signal must be bool"

        for list_key in ("expected_rule_families", "must_include", "must_not_contain"):
            value = fixture[list_key]
            assert isinstance(value, list) and value, f"{fid}: '{list_key}' must be non-empty"
            assert all(isinstance(item, str) and item.strip() for item in value), (
                f"{fid}: '{list_key}' has empty entries"
            )


@pytest.mark.parametrize("face", ["family_shield", "seller_guard"])
def test_expected_families_exist_in_the_rule_pack(face: str) -> None:
    """Every expected family must be modeled by the face's rule pack (else it can never fire)."""
    pack_families = _families_for(face)
    problems: list[str] = []
    for fixture in _load(face):
        unknown = set(fixture["expected_rule_families"]) - pack_families
        if unknown:
            problems.append(f"{fixture['id']}: families not in {face} pack: {sorted(unknown)}")
    assert not problems, "\n".join(problems)


def test_seller_guard_fixtures_forbid_claiming_money_arrived() -> None:
    confirmed = {_norm(phrase) for phrase in SG_MONEY_CONFIRMED}
    for fixture in _load("seller_guard"):
        forbidden = {_norm(item) for item in fixture["must_not_contain"]}
        assert forbidden & confirmed, (
            f"{fixture['id']}: must_not_contain should forbid a 'money arrived' phrase (§8)"
        )
