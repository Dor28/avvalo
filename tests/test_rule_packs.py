"""Pre-authored unified rule-pack integrity tests.

The YAML files under ``rules/`` are hand-authored, safety-critical assets. These
tests validate them directly against the current loader schema and allowed family
taxonomy.
"""

from pathlib import Path

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

RULES_DIR = "rules"
FROZEN_RULE_ID_PREFIX = "fs."


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


def test_required_families_present() -> None:
    present = {family["family"] for family in _load_families(RULES_DIR)}

    missing = FAMILY_REQUIRED - present
    assert not missing, f"missing required families {missing}"

    unexpected = present - FAMILY_ALLOWED
    assert not unexpected, f"unexpected rule families {unexpected}"


def test_every_family_has_rules() -> None:
    for family in _load_families(RULES_DIR):
        assert family.get("family"), "a family entry is missing its `family:` name"
        assert family.get("rules"), f"family '{family.get('family')}' has no rules"


def test_rule_ids_unique_and_keep_the_frozen_prefix() -> None:
    ids = [rule["id"] for rule in _all_rules(RULES_DIR)]

    assert len(ids) == len(set(ids)), f"duplicate rule ids {sorted(ids)}"
    bad_prefix = [rid for rid in ids if not rid.startswith(FROZEN_RULE_ID_PREFIX)]
    assert not bad_prefix, (
        f"rule ids must keep the frozen '{FROZEN_RULE_ID_PREFIX}' prefix: {bad_prefix}"
    )


def test_each_rule_matches_the_schema() -> None:
    problems: list[str] = []
    for rule in _all_rules(RULES_DIR):
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
    families = {f["family"] for f in _load_families(RULES_DIR)}
    assert {
        "receipt_inconsistency",
        "amount_mismatch",
        "edited_screenshot_hint",
        "fake_courier_refund",
    } <= families
