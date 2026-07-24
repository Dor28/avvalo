"""Detected high-severity rule preservation and retry tests."""

from __future__ import annotations

import pytest

from app.engine import CheckInput, CheckStatus, InputType, Language, run_check
from app.engine.llm import LLMResponse
from app.engine.types import DraftOutput, RuleHit
from app.engine.validate import ValidationReason, validate

HITS = [
    RuleHit(rule_id="fs.authority.impersonation", family="authority", message_key="a", severity=3),
    RuleHit(rule_id="fs.credential.otp", family="credential", message_key="b", severity=3),
    RuleHit(rule_id="fs.urgency.deadline", family="urgency", message_key="c", severity=2),
]


def _draft(addressed: list[str]) -> DraftOutput:
    return DraftOutput(
        red_flags=["The supplied content contains authoritative warning facts."],
        verify=["Use an independent official channel."],
        ask=["What can be confirmed independently?"],
        addressed_rule_ids=addressed,
    )


@pytest.mark.parametrize("language", list(Language))
def test_multiple_rule_facts_reject_partial_and_accept_complete(language: Language) -> None:
    partial = validate(_draft([HITS[0].rule_id]), [], HITS, language)
    complete = validate(_draft([hit.rule_id for hit in HITS]), [], HITS, language)

    assert partial.ok is False
    assert partial.reason is ValidationReason.MISSING_RULE_IDS
    assert complete.ok is True


def test_zero_rule_behavior_is_unchanged() -> None:
    result = validate(_draft([]), [], [], Language.ru)
    assert result.ok is True


class _SequenceProvider:
    def __init__(self, drafts: list[DraftOutput]) -> None:
        self.drafts = drafts
        self.calls: list[dict] = []

    async def analyze(self, **kwargs) -> LLMResponse:
        self.calls.append(kwargs)
        draft = self.drafts[min(len(self.calls) - 1, len(self.drafts) - 1)]
        return LLMResponse(draft=draft, input_tokens=10, output_tokens=5)


async def test_missing_rule_ids_use_retry_then_succeed() -> None:
    complete_ids = [
        "fs.authority.impersonation",
        "fs.credential.otp",
        "fs.urgency.deadline",
    ]
    provider = _SequenceProvider([_draft(complete_ids[:1]), _draft(complete_ids)])

    result = await run_check(
        CheckInput(
                        user_key="rule-retry",
            language=Language.uz_latn,
            input_type=InputType.text,
            raw_text=(
                "Bank xavfsizlik xizmatidanmiz. Kartangiz bloklanadi. "
                "Hozir SMS kodni yuboring."
            ),
        ),
        llm_provider=provider,
    )

    assert result.status == CheckStatus.ok
    assert len(provider.calls) == 2
    assert "missing addressed rule ids" in provider.calls[1]["system"]


async def test_missing_rule_ids_twice_uses_existing_safety_fallback() -> None:
    provider = _SequenceProvider([_draft(["fs.authority.impersonation"])])
    result = await run_check(
        CheckInput(
                        user_key="rule-fallback",
            language=Language.ru,
            input_type=InputType.text,
            raw_text=(
                "Bank xavfsizlik xizmatidanmiz. Kartangiz bloklanadi. "
                "Hozir SMS kodni yuboring."
            ),
        ),
        llm_provider=provider,
    )

    assert result.status == CheckStatus.safety_fallback
    assert result.safety_blocked is True
    assert len(provider.calls) == 2
