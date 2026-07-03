"""T5 — rule engine, family rules & minimization (V1_TECHNICAL_PLAN §10, §11, §13 T5).

Acceptance criteria covered:
- each family golden input fires its expected rule families (and yields >=1 hit);
- minimization tokenizes PII while preserving the link signal (§10 unit test);
- structural extractors classify links and transfer-to-card phrasing into signals.
"""

import pytest

from app.engine.minimize import minimize
from app.engine.rules import load_rule_pack, run_rules
from app.engine.rules.engine import (
    classify_link,
    extract_structural_signals,
    normalize_text,
)


def test_rule_packs_load_with_description_map() -> None:
    for face in ("family", "merchants"):
        pack = load_rule_pack(face)
        assert pack.rules, f"{face}: no rules loaded"
        for rule in pack.rules:
            assert pack.descriptions[rule.id] == rule.desc


def test_unknown_face_is_rejected() -> None:
    with pytest.raises(ValueError):
        load_rule_pack("no_such_face")


def test_family_goldens_fire_expected_families(golden) -> None:
    for fixture in golden("family"):
        hits, _ = run_rules(fixture["input"], "family")
        assert hits, f"{fixture['id']}: expected at least one rule hit"
        families = {hit.family for hit in hits}
        missing = set(fixture["expected_rule_families"]) - families
        assert not missing, f"{fixture['id']}: expected families did not fire: {sorted(missing)}"


def test_minimize_tokenizes_pii_and_keeps_link_signal() -> None:
    # §10 unit test: phone + lookalike URL + card -> tokens, no raw values.
    raw = (
        "Karta: 8600 1234 1234 5678, tel +998 90 123 45 67, "
        "to'lov havolasi https://click-uz.example/pay"
    )
    out = minimize(raw)

    assert "[CARD]" in out
    assert "[PHONE]" in out
    assert "[LINK: lookalike-domain]" in out
    for leaked in ("8600", "click-uz.example", "90 123 45 67"):
        assert leaked not in out, f"raw value leaked through minimization: {leaked!r}"


def test_minimize_tokenizes_email_and_handle() -> None:
    out = minimize("Yozing: support@bank.example yoki @bank_help kanaliga")
    assert "[EMAIL]" in out
    assert "[HANDLE]" in out
    assert "support@bank.example" not in out


@pytest.mark.parametrize("passport", ["AA1234567", "aa 1234567"])
def test_minimize_tokenizes_passport_like_ids(passport: str) -> None:
    out = minimize(f"Pasport ma'lumotini yuboring: {passport}")
    assert "[PASSPORT]" in out
    assert passport not in out


def test_classify_link_labels_shortener_lookalike_and_legit() -> None:
    assert classify_link("https://bit.ly/abc") == "shortened"
    assert classify_link("https://payme-secure.example") == "lookalike-domain"
    assert classify_link("https://payme.uz/pay") is None
    assert classify_link("https://example.com") is None


def test_normalize_text_lowercases_and_unifies_apostrophes() -> None:
    assert normalize_text("BANK Xavfsizlik") == "bank xavfsizlik"
    curly = "o" + chr(0x2018) + "tkaz"
    assert normalize_text(curly) == normalize_text("o'tkaz")


def test_transfer_to_card_phrasing_emits_card_personal_signal() -> None:
    signals = extract_structural_signals("Shu kartaga 8600123412345678 pul tashlang")
    kinds = {signal.kind for signal in signals}
    assert "card_personal" in kinds
    assert "card" in kinds
