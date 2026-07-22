"""Direct contract tests for prompt assembly and deterministic cost accounting."""

from pathlib import Path

from app.engine.llm.prompt import build_prompt
from app.engine.types import Language, RuleHit
from app.obs.cost import estimate_llm_cost_usd

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_build_prompt_uses_single_checker_contract_and_grounds_the_text() -> None:
    hits = [
        RuleHit(
            rule_id="fs.credential.otp",
            family="credential_theft",
            message_key="otp_request",
            severity=3,
        )
    ]
    system, user = build_prompt(
        language=Language.ru,
        minimized_text="minimized [CODE] body",
        rule_hits=hits,
        signals=[],
    )

    safety = (REPO_ROOT / "prompts" / "system_safety.txt").read_text(encoding="utf-8")
    assert system.strip() == safety.strip()
    assert "minimized [CODE] body" in user, "minimized text must be embedded in the user prompt"
    assert "fs.credential.otp" in user, "the supplied rule hit must be grounded into the prompt"
    assert "{knowledge}" not in user


def test_cost_formula_uses_configured_per_million_token_rates() -> None:
    result = estimate_llm_cost_usd(
        input_tokens=1_000_000,
        output_tokens=2_000_000,
        in_rate_per_m=1.0,
        out_rate_per_m=3.0,
    )

    assert result == 7.0
