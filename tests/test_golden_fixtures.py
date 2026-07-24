"""Golden-fixture integrity tests for the unified consumer checker.

Payment, courier, and refund scenarios live in the same family set as the
original consumer examples.
"""

import json
from pathlib import Path

import yaml

from app.engine.rules.loader import RULE_PACK_DIR
from app.engine.types import InputType, Language

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = REPO_ROOT / "tests" / "fixtures" / "golden"

REQUIRED_KEYS = {
    "id",
    "language",
    "input_type",
    "input",
    "expected_rule_families",
    "must_include",
    "must_not_contain",
    "no_signal",
}

# Payment fixtures must never imply that an incoming payment was confirmed.
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


def _load() -> list[dict]:
    data = json.loads((GOLDEN_DIR / "checks.json").read_text(encoding="utf-8"))
    assert isinstance(data, list), "checks.json must be a JSON array"
    return data


def _pack_families() -> set[str]:
    families: set[str] = set()
    for path in sorted(RULE_PACK_DIR.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        families.update(f["family"] for f in doc["families"])
    return families


def test_minimum_golden_counts() -> None:
    assert len(_load()) >= 8


def test_fixture_shape_and_values() -> None:
    valid_languages = {lang.value for lang in Language}
    valid_input_types = {it.value for it in InputType}
    seen_ids: set[str] = set()

    for fixture in _load():
        fid = fixture.get("id", "<no-id>")
        missing = REQUIRED_KEYS - fixture.keys()
        assert not missing, f"{fid}: missing keys {missing}"

        assert fixture["id"] not in seen_ids, f"duplicate fixture id {fixture['id']}"
        seen_ids.add(fixture["id"])

        assert fixture["language"] in valid_languages, f"{fid}: bad language {fixture['language']}"
        assert fixture["input_type"] in valid_input_types, f"{fid}: bad input_type"
        assert isinstance(fixture["input"], str) and fixture["input"].strip(), f"{fid}: empty input"
        assert isinstance(fixture["no_signal"], bool), f"{fid}: no_signal must be bool"

        for list_key in ("expected_rule_families", "must_include", "must_not_contain"):
            value = fixture[list_key]
            assert isinstance(value, list), f"{fid}: '{list_key}' must be a list"
            if list_key != "expected_rule_families" or fixture["input_type"] == "text":
                assert value, f"{fid}: '{list_key}' must be non-empty"
            assert all(isinstance(item, str) and item.strip() for item in value), (
                f"{fid}: '{list_key}' has empty entries"
            )

        if fixture["input_type"] == "image":
            assert fixture.get("expected_status") in {"ok", "low_ocr"}, (
                f"{fid}: bad expected_status"
            )
            signal_kinds = fixture.get("expected_signal_kinds")
            assert isinstance(signal_kinds, list), f"{fid}: expected_signal_kinds must be a list"
            assert (GOLDEN_DIR / fixture["input"]).is_file(), f"{fid}: image fixture is missing"


def test_expected_families_exist_in_the_rule_pack() -> None:
    """Every expected family must be modeled by the rule pack (else it can never fire)."""
    pack_families = _pack_families()
    problems: list[str] = []
    for fixture in _load():
        unknown = set(fixture["expected_rule_families"]) - pack_families
        if unknown:
            problems.append(f"{fixture['id']}: families not in the pack: {sorted(unknown)}")
    assert not problems, "\n".join(problems)


def test_payment_fixtures_forbid_claiming_money_arrived() -> None:
    confirmed = {_norm(phrase) for phrase in SG_MONEY_CONFIRMED}
    payment_fixtures = [
        fixture
        for fixture in _load()
        if fixture["id"].startswith("fs_") and fixture["id"] >= "fs_06"
    ]
    for fixture in payment_fixtures:
        forbidden = {_norm(item) for item in fixture["must_not_contain"]}
        assert forbidden & confirmed, (
            f"{fixture['id']}: must_not_contain should forbid a 'money arrived' phrase"
        )
