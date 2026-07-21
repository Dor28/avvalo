"""Regression tests for code-review fixes.

Covers three bugs found during review that the existing suite did not exercise:

1. ``minimize`` left raw phone numbers with operator codes 50/55/88/20 in the
   text sent to the model (privacy leak).
2. The merchants face's always-on severity-1 reminder forced the validator to reject
   benign payment checks for having no red flags, pushing them to the fallback.
3. Failed / empty checks consumed a daily-limit slot.
"""

import pytest

from app.data import repo
from app.engine import CheckInput, CheckStatus, InputType, Language, run_check
from app.engine.llm import LLMResponse
from app.engine.llm.base import LLMProviderError
from app.engine.minimize import minimize
from app.engine.rules import run_rules
from app.engine.rules.engine import extract_structural_signals
from app.engine.types import DraftOutput, RuleHit
from app.engine.validate import validate
from tests.support import addressed_rule_ids

# --- Fix #1: phone redaction across all Uzbek operator prefixes -------------

@pytest.mark.parametrize(
    "number",
    [
        "+998 90 123 45 67",  # Beeline (already worked)
        "+998 88 123 45 67",  # Mobiuz/UMS — previously leaked
        "+998 50 123 45 67",  # Ucell/Mobiuz — previously leaked
        "+998 55 502 11 22",  # Perfectum — previously leaked
        "+998 20 123 45 67",  # newer allocation — previously leaked
        "+998 33 123 45 67",  # Humans (already worked)
    ],
)
def test_minimize_redacts_all_uz_operator_prefixes(number: str) -> None:
    out = minimize(f"Mana raqamim: {number}")
    assert "[PHONE]" in out
    # No run of the original phone digits survives minimization.
    assert number not in out
    assert "123 45 67" not in out
    assert "502 11 22" not in out


@pytest.mark.parametrize("prefix", ["88", "50", "55", "20"])
def test_phone_signal_emitted_for_previously_missed_prefixes(prefix: str) -> None:
    signals = extract_structural_signals(f"Qo'ng'iroq qiling: +998 {prefix} 123 45 67")
    assert "phone" in {signal.kind for signal in signals}


# --- Fix #2: severity-gated red_flags requirement ---------------------------

def test_benign_merchants_message_passes_with_no_red_flags() -> None:
    benign = "Assalomu alaykum, men karta orqali to'lov qildim, rahmat."
    hits, signals = run_rules(benign, "merchants")

    # Only the always-on severity-1 reminder should fire here.
    assert [hit.rule_id for hit in hits] == ["sg.verify.always"]

    draft = DraftOutput(
        red_flags=[],
        pattern=None,
        verify=["Open your own bank app and confirm the incoming transfer yourself."],
        ask=["Which account name and exact amount does your statement show?"],
    )
    result = validate(draft, signals, hits, Language.uz_latn)
    assert result.ok, result.reason


def test_high_severity_hit_still_requires_red_flags() -> None:
    # The safety property must hold: a real (severity>=2) signal with an empty
    # red_flags block is still rejected.
    hits = [
        RuleHit(rule_id="sg.amount.overpay", family="amount_mismatch",
                message_key="amount_mismatch", severity=3),
    ]
    draft = DraftOutput(
        red_flags=[],
        verify=["Confirm the real incoming transfer in your bank app."],
        ask=["Why is a refund needed before the money clears?"],
    )
    result = validate(draft, [], hits, Language.uz_latn)
    assert not result.ok
    assert result.reason == "red_flags block is empty despite detected signals"


class _EmptyRedFlagsLLM:
    """Well-behaved model: returns no red flags for benign input."""

    async def analyze(self, **kwargs) -> LLMResponse:
        return LLMResponse(
            draft=DraftOutput(
                red_flags=[],
                pattern=None,
                verify=["Open your bank app and confirm the transfer before shipping."],
                ask=["Which payment record matches this order?"],
                addressed_rule_ids=addressed_rule_ids(kwargs["user"]),
            ),
            input_tokens=20,
            output_tokens=10,
        )


async def test_benign_merchants_check_is_ok_not_safety_fallback(session) -> None:
    result = await run_check(
        CheckInput(
            face="merchants",
            user_key="sg-benign",
            language=Language.uz_latn,
            input_type=InputType.text,
            raw_text="Assalomu alaykum, karta orqali to'lov qildim, rahmat.",
        ),
        session=session,
        llm_provider=_EmptyRedFlagsLLM(),
    )
    assert result.status == CheckStatus.ok
    assert result.safety_blocked is False


# --- Fix #3: failed / empty checks must not burn the daily quota ------------

class _OkLLM:
    async def analyze(self, **kwargs) -> LLMResponse:
        return LLMResponse(
            draft=DraftOutput(
                red_flags=["The message asks for a one-time code."],
                verify=["Open the official app yourself."],
                ask=["Which official channel shows this request?"],
                addressed_rule_ids=addressed_rule_ids(kwargs["user"]),
            ),
            input_tokens=10,
            output_tokens=5,
        )


class _BoomLLM:
    async def analyze(self, **_kwargs) -> LLMResponse:
        raise LLMProviderError("provider down")


async def test_empty_input_does_not_consume_quota(session) -> None:
    result = await run_check(
        CheckInput(
            face="family", user_key="q-empty", language=Language.ru,
            input_type=InputType.text, raw_text="   ",
        ),
        session=session,
        llm_provider=_OkLLM(),
    )
    assert result.status == CheckStatus.empty_input
    assert await repo.get_usage(session, user_key="q-empty", face="family") == 0


async def test_llm_error_does_not_consume_quota(session) -> None:
    result = await run_check(
        CheckInput(
            face="family", user_key="q-err", language=Language.ru,
            input_type=InputType.text,
            raw_text="Bank xavfsizlik xizmati. SMS kodni yuboring.",
        ),
        session=session,
        llm_provider=_BoomLLM(),
    )
    assert result.status == CheckStatus.llm_error
    assert await repo.get_usage(session, user_key="q-err", face="family") == 0


async def test_successful_check_consumes_quota(session) -> None:
    await run_check(
        CheckInput(
            face="family", user_key="q-ok", language=Language.ru,
            input_type=InputType.text,
            raw_text="Bank xavfsizlik xizmati. SMS kodni yuboring.",
        ),
        session=session,
        llm_provider=_OkLLM(),
    )
    assert await repo.get_usage(session, user_key="q-ok", face="family") == 1


async def test_rate_limited_attempts_do_not_grow_the_counter(session) -> None:
    from app.engine.faces import FACES

    limit = FACES["family"].daily_limit
    check_input = CheckInput(
        face="family", user_key="q-cap", language=Language.ru,
        input_type=InputType.text,
        raw_text="Bank xavfsizlik xizmati. SMS kodni yuboring.",
    )
    statuses = [
        (await run_check(check_input, session=session, llm_provider=_OkLLM())).status
        for _ in range(limit + 3)
    ]
    assert statuses[:limit] == [CheckStatus.ok] * limit
    assert statuses[limit:] == [CheckStatus.rate_limited] * 3
    # Over-limit rejections are refunded, so the counter pins at the limit
    # instead of growing without bound.
    assert await repo.get_usage(session, user_key="q-cap", face="family") == limit
