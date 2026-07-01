"""T10 — Seller Guard face (V1_TECHNICAL_PLAN §11, §13 T10).

The full end-to-end SG check needs the LLM stage (T6) and runs against a live
model, so it is not asserted offline here. What is deterministic — and is the
heart of T10 — is that each SG golden fires its expected families and that the
always-on "verify in your bank app" reminder fires on every payment check.
"""

from app.config import Settings
from app.engine import CheckInput, CheckStatus, InputType, Language, run_check
from app.engine.llm import LLMResponse
from app.engine.rules import run_rules
from app.engine.types import DraftOutput
from app.main import PLACEHOLDER_TOKEN, configured_bot_specs


class SellerGuardLLMProvider:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def analyze(self, **kwargs) -> LLMResponse:
        self.calls.append(kwargs)
        assert "money has arrived" in kwargs["user"]
        return LLMResponse(
            draft=DraftOutput(
                red_flags=[
                    "A screenshot or message is not proof of payment.",
                    "The request pressures you to act before confirming your balance.",
                ],
                pattern="Payment proof pressure.",
                verify=[
                    "Open your own bank app and confirm the incoming transfer "
                    "before handing over goods."
                ],
                ask=["Ask the buyer which official payment record matches this order."],
            ),
            input_tokens=100,
            output_tokens=40,
        )


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


async def test_seller_guard_goldens_pass_same_run_check_path(session, golden) -> None:
    provider = SellerGuardLLMProvider()
    fixtures = golden("seller_guard")

    for index, fixture in enumerate(fixtures):
        result = await run_check(
            CheckInput(
                face="seller_guard",
                user_key=f"sg-e2e-{index}",
                language=Language(fixture["language"]),
                input_type=InputType(fixture["input_type"]),
                raw_text=fixture["input"],
            ),
            session=session,
            llm_provider=provider,
        )

        assert result.status == CheckStatus.ok
        text = (result.text or "").casefold()
        for forbidden in fixture["must_not_contain"]:
            assert forbidden.casefold() not in text
        assert "money has arrived" not in text
        assert "payment is genuine" not in text

    assert len(provider.calls) == len(fixtures)


def test_process_uses_single_telegram_token_for_family_shield() -> None:
    settings = _settings(telegram_token="bot-token")

    specs = configured_bot_specs(settings)

    assert [spec.face_id for spec in specs] == ["family_shield"]
    assert [spec.token for spec in specs] == ["bot-token"]


def test_process_ignores_placeholder_telegram_token() -> None:
    settings = _settings(telegram_token=PLACEHOLDER_TOKEN)

    specs = configured_bot_specs(settings)

    assert specs == []


def test_process_ignores_empty_telegram_token() -> None:
    settings = _settings(telegram_token="")

    specs = configured_bot_specs(settings)

    assert specs == []


def _settings(**overrides) -> Settings:
    values = {
        "telegram_token": "bot-token",
        "database_url": "postgresql+asyncpg://avvalo:avvalo@localhost:5432/avvalo",
        "app_hmac_secret": "test-hmac-secret",
        "llm_base_url": "http://localhost:11434/v1",
        "llm_api_key": "ollama",
        "llm_model": "qwen2.5:7b-instruct",
        "web_session_secret": "test-web-session-secret",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _seller_guard_rules():
    from app.engine.rules import load_rule_pack

    return load_rule_pack("seller_guard").rules
