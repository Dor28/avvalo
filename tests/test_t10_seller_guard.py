"""T10 — Seller Guard face (V1_TECHNICAL_PLAN §11, §13 T10).

The full end-to-end SG check needs the LLM stage (T6) and runs against a live
model, so it is not asserted offline here. What is deterministic — and is the
heart of T10 — is that each SG golden fires its expected families and that the
always-on "verify in your bank app" reminder fires on every payment check.
"""

from app.engine.rules import run_rules


def test_seller_guard_goldens_fire_expected_families(golden) -> None:
    for fixture in golden("seller_guard"):
        hits, _ = run_rules(fixture["input"], "seller_guard")
        assert hits, f"{fixture['id']}: expected at least one rule hit"
        families = {hit.family for hit in hits}
        missing = set(fixture["expected_rule_families"]) - families
        assert not missing, f"{fixture['id']}: expected families did not fire: {sorted(missing)}"


def test_verify_in_bank_app_reminder_always_fires(golden) -> None:
    # §11: SG's hard rule — every payment-related check ends with "verify it yourself".
    for fixture in golden("seller_guard"):
        hits, _ = run_rules(fixture["input"], "seller_guard")
        families = {hit.family for hit in hits}
        assert "verify_in_bank_app" in families, f"{fixture['id']}: missing bank-verify reminder"


def test_seller_guard_uses_its_own_rule_pack_only(golden) -> None:
    """Families fired for SG inputs must all come from the SG pack (no FS bleed-through)."""
    sg_families = {rule.family for rule in _seller_guard_rules()}
    for fixture in golden("seller_guard"):
        hits, _ = run_rules(fixture["input"], "seller_guard")
        assert {hit.family for hit in hits} <= sg_families


def _seller_guard_rules():
    from app.engine.rules import load_rule_pack

    return load_rule_pack("seller_guard").rules
