"""Pre-authored rule-pack integrity tests (V1_TECHNICAL_PLAN §11).

The YAML packs under ``rules/`` are hand-authored, safety-critical assets that
the plan says to *use, not regenerate* (§0.6). The rule engine/loader (T5) is
not built yet, so these tests validate the packs directly against the §11
schema and the required-family list — the same contract the loader will enforce.
"""

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

LANGUAGES = ("uz_latn", "uz_cyrl", "ru")

# Signal kinds the engine knows about (§6 Signal.kind / §10 minimization tokens).
ALLOWED_SIGNALS = {
    "otp_request",
    "card_personal",
    "link_lookalike",
    "link_shortened",
    "phone_new",
}

# Required + allowed families for the unified checker.
FAMILY_REQUIRED = {
    "credential_theft",
    "urgency_secrecy",
    "authority_impersonation",
    "upfront_payment",
    "verification_avoidance",
}
FAMILY_ALLOWED = FAMILY_REQUIRED | {
    "implausible_promise",
    "suspicious_link_qr",
    "receipt_inconsistency",
    "amount_mismatch",
    "edited_screenshot_hint",
    "fake_courier_refund",
}

PACKS = {
    "family": {
        "dir": "rules/checker",
        "id_prefix": "fs.",
        "required_families": FAMILY_REQUIRED,
        "allowed_families": FAMILY_ALLOWED,
    },
}


def _load_families(pack_dir: str) -> list[dict]:
    """Flatten every ``families:`` entry across all YAML files in the dir (§11 loader)."""
    families: list[dict] = []
    paths = sorted((REPO_ROOT / pack_dir).glob("*.yaml"))
    assert paths, f"no YAML rule files found under {pack_dir}"
    for path in paths:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict) and isinstance(data.get("families"), list), (
            f"{path} must have a top-level `families:` list (§11)"
        )
        families.extend(data["families"])
    return families


def _all_rules(pack_dir: str) -> list[dict]:
    rules: list[dict] = []
    for family in _load_families(pack_dir):
        rules.extend(family["rules"])
    return rules


@pytest.mark.parametrize("face", PACKS)
def test_required_families_present(face: str) -> None:
    cfg = PACKS[face]
    present = {family["family"] for family in _load_families(cfg["dir"])}

    missing = cfg["required_families"] - present
    assert not missing, f"{face}: missing required families {missing}"

    unexpected = present - cfg["allowed_families"]
    assert not unexpected, f"{face}: families not allowed by §11 {unexpected}"


@pytest.mark.parametrize("face", PACKS)
def test_every_family_has_rules(face: str) -> None:
    for family in _load_families(PACKS[face]["dir"]):
        assert family.get("family"), "a family entry is missing its `family:` name"
        assert family.get("rules"), f"family '{family.get('family')}' has no rules"


@pytest.mark.parametrize("face", PACKS)
def test_rule_ids_unique_and_namespaced(face: str) -> None:
    cfg = PACKS[face]
    ids = [rule["id"] for rule in _all_rules(cfg["dir"])]

    assert len(ids) == len(set(ids)), f"{face}: duplicate rule ids {sorted(ids)}"
    bad_prefix = [rid for rid in ids if not rid.startswith(cfg["id_prefix"])]
    assert not bad_prefix, f"{face}: rule ids must start with '{cfg['id_prefix']}': {bad_prefix}"


@pytest.mark.parametrize("face", PACKS)
def test_each_rule_matches_the_schema(face: str) -> None:
    problems: list[str] = []
    for rule in _all_rules(PACKS[face]["dir"]):
        rid = rule.get("id", "<no-id>")

        for field in ("id", "desc", "message_key"):
            if not isinstance(rule.get(field), str) or not rule[field].strip():
                problems.append(f"{rid}: '{field}' must be a non-empty string")

        severity = rule.get("severity")
        if not isinstance(severity, int) or isinstance(severity, bool) or not 1 <= severity <= 3:
            problems.append(f"{rid}: 'severity' must be an int in 1..3, got {severity!r}")

        emits = rule.get("emits_signal")
        if emits is not None and emits not in ALLOWED_SIGNALS:
            problems.append(f"{rid}: emits_signal '{emits}' not in {sorted(ALLOWED_SIGNALS)}")

        match = rule.get("match")
        if not isinstance(match, dict):
            problems.append(f"{rid}: 'match' must be a mapping of language -> keywords")
            continue
        for lang in LANGUAGES:
            kws = match.get(lang)
            if not isinstance(kws, list) or not kws:
                problems.append(f"{rid}: match.{lang} must be a non-empty keyword list")
                continue
            for kw in kws:
                if not isinstance(kw, str) or not kw.strip():
                    problems.append(f"{rid}: match.{lang} contains an empty keyword")
                elif kw != kw.lower():
                    # Matching is case-insensitive on lowercased text (§11); an
                    # uppercase keyword could never fire.
                    problems.append(f"{rid}: match.{lang} keyword not lowercase: {kw!r}")

    assert not problems, "rule schema violations:\n" + "\n".join(problems)


def test_consumer_pack_includes_payment_screenshot_and_refund_protection() -> None:
    families = {f["family"] for f in _load_families(PACKS["family"]["dir"])}
    assert {
        "receipt_inconsistency",
        "amount_mismatch",
        "edited_screenshot_hint",
        "fake_courier_refund",
    } <= families
