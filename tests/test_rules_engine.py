"""T5 deterministic rule-engine and minimization tests."""

import json
from pathlib import Path

from app.engine.minimize import minimize
from app.engine.rules import load_rule_pack, run_rules

_ROOT = Path(__file__).resolve().parents[1]
_GOLDEN_PATH = _ROOT / "tests" / "fixtures" / "golden" / "checks.json"

_EXPECTED_FS_RULE_IDS = {
    "fs_01_fake_bank_support": {
        "fs.credential.otp",
        "fs.urgency.deadline",
        "fs.authority.impersonation",
    },
    "fs_02_family_emergency": {
        "fs.authority.impersonation",
        "fs.urgency.deadline",
        "fs.secrecy.tell_nobody",
        "fs.payment.prepay",
    },
    "fs_03_seller_prepayment": {
        "fs.urgency.deadline",
        "fs.payment.prepay",
        "fs.verify.avoids",
        "fs.promise.toogood",
    },
    "fs_04_fake_delivery_link": {
        "fs.urgency.deadline",
        "fs.payment.prepay",
        "fs.link.payorlogin",
    },
    "fs_05_upfront_fee_job": {
        "fs.promise.toogood",
        "fs.urgency.deadline",
        "fs.payment.prepay",
        "fs.credential.secret_docs",
    },
    "fs_06_incoming_payment_screenshot": {
        "fs.payment.receipt_inconsistent",
        "fs.payment.screenshot_claim",
        "fs.payment.release_pressure",
    },
    "fs_07_overpayment_refund": {
        "fs.payment.overpayment_refund",
        "fs.payment.screenshot_claim",
    },
    "fs_08_payment_name_mismatch": {
        "fs.payment.receipt_inconsistent",
        "fs.payment.screenshot_claim",
        "fs.payment.release_pressure",
    },
}


def test_loader_flattens_family_pack() -> None:
    pack = load_rule_pack()

    rule_ids = {rule.id for rule in pack.rules}
    assert _EXPECTED_FS_RULE_IDS["fs_01_fake_bank_support"].issubset(rule_ids)
    assert pack.descriptions["fs.credential.otp"].startswith("Asks for an SMS")


def test_golden_inputs_fire_expected_rules() -> None:
    fixtures = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))

    for fixture in fixtures:
        hits, _signals = run_rules(fixture["input"])
        hit_ids = {hit.rule_id for hit in hits}
        hit_families = {hit.family for hit in hits}

        assert _EXPECTED_FS_RULE_IDS[fixture["id"]].issubset(hit_ids), fixture["id"]
        assert set(fixture["expected_rule_families"]).issubset(hit_families), fixture["id"]
        assert hits, fixture["id"]


def test_minimization_tokenizes_pii_and_preserves_link_signal() -> None:
    raw_text = (
        "Ali Valiyev, sms kod 123456 ni yuboring. "
        "Tel: +998 90 123 45 67, karta 8600 1234 1234 5678, "
        "email test@example.com, admin @payme_help, link hxxps://payme-secure[.]example/a."
    )

    _hits, signals = run_rules(raw_text)
    minimized = minimize(raw_text, signals)
    signal_pairs = {(signal.kind, signal.note) for signal in signals}

    assert ("link_lookalike", "lookalike-domain") in signal_pairs
    assert "[PHONE]" in minimized
    assert "[CARD]" in minimized
    assert "[EMAIL]" in minimized
    assert "[HANDLE]" in minimized
    assert "[CODE]" in minimized
    assert "[LINK: lookalike-domain]" in minimized
    assert "+998 90 123 45 67" not in minimized
    assert "8600 1234 1234 5678" not in minimized
    assert "test@example.com" not in minimized
    assert "payme-secure" not in minimized
