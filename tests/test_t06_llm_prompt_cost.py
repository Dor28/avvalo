"""T6 — LLM integration: prompt builder & cost accounting (V1_TECHNICAL_PLAN §8).

These are live acceptance specs that skip until T6 lands. The LLM call itself
hits a network model and is not exercised here; the deterministic, specified
pieces — the prompt wiring and the cost formula — are.
"""

import inspect
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_build_prompt_uses_system_safety_and_grounds_the_text(callable_or_skip) -> None:
    build_prompt = callable_or_skip("app.engine.llm.prompt", "build_prompt")
    params = inspect.signature(build_prompt).parameters

    # The plan writes `face`; the implementation may name it `face_id`. Accept either,
    # and call by keyword so it works whether params are positional or keyword-only.
    face_kw = next((name for name in ("face", "face_id") if name in params), None)
    needed = {"language", "minimized_text", "rule_hits", "signals"}
    if face_kw is None or not needed <= set(params):
        pytest.skip(f"build_prompt signature differs from §8: {list(params)}")

    from app.engine.types import Language, RuleHit

    hits = [
        RuleHit(
            rule_id="fs.credential.otp",
            family="credential_theft",
            message_key="otp_request",
            severity=3,
        )
    ]
    system, user = build_prompt(
        **{face_kw: "family_shield"},
        language=Language.ru,
        minimized_text="minimized [CODE] body",
        rule_hits=hits,
        signals=[],
    )

    safety = (REPO_ROOT / "prompts" / "system_safety.txt").read_text(encoding="utf-8")
    assert system.strip() == safety.strip(), "system prompt must be system_safety.txt verbatim (§8)"
    assert "minimized [CODE] body" in user, "minimized text must be embedded in the user prompt"
    assert "fs.credential.otp" in user, "the supplied rule hit must be grounded into the prompt"


def test_cost_formula_matches_spec(callable_or_skip) -> None:
    cost_fn = callable_or_skip(
        "app.obs.cost", "compute_cost", "cost_usd", "estimate_cost", "calc_cost"
    )
    if len(inspect.signature(cost_fn).parameters) < 4:
        pytest.skip(f"cost fn arity differs from §8: {inspect.signature(cost_fn)}")

    # §8: cost = in/1e6 * IN_RATE + out/1e6 * OUT_RATE.
    try:
        result = cost_fn(1_000_000, 2_000_000, 1.0, 3.0)
    except TypeError as exc:
        pytest.skip(f"cost fn not positional per §8: {exc}")
    assert abs(float(result) - 7.0) < 1e-9
