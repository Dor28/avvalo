"""Coverage for the model-judged off-topic redirect (V1_TECHNICAL_PLAN §5.1).

``app.engine.meta`` catches a fixed list of chatter phrases before any provider
is touched. It cannot catch open-ended non-situations — "what day is it" reached
the fraud-check prompt and came back as a situation card advising the user to
verify today's date. This module covers the model-side triage that closes that
gap, and the guards that keep it from swallowing a real situation.
"""

import json

from app.data import repo
from app.engine import (
    CheckInput,
    CheckStatus,
    InputType,
    Language,
    SituationType,
    run_check,
)
from app.engine.format import format_status_message
from app.engine.llm import LLMResponse, draft_output_schema
from app.engine.types import DraftOutput
from tests.support import addressed_rule_ids

# Latin-script Uzbek so the resolved reply language is unambiguous: the draft
# below must be in the same script or the validator rejects it for that reason
# instead of exercising the override under test.
_SUSPICIOUS_MESSAGE = "Salom, kartangiz bloklandi, hozir kod yuboring."


class _OffTopicLLM:
    """A model classifying the content as not a situation, per the contract."""

    def __init__(self) -> None:
        self.calls = 0

    async def analyze(self, **kwargs) -> LLMResponse:
        self.calls += 1
        return LLMResponse(
            draft=DraftOutput(situation_type=SituationType.off_topic),
            input_tokens=8,
            output_tokens=2,
        )


class _MislabellingLLM:
    """A model wrongly calling a real situation off-topic, but still analyzing it."""

    def __init__(self) -> None:
        self.calls = 0

    async def analyze(self, **kwargs) -> LLMResponse:
        self.calls += 1
        return LLMResponse(
            draft=DraftOutput(
                situation_type=SituationType.off_topic,
                red_flags=["Xabar bir martalik kodni so'rayapti"],
                verify=["Bank ilovasini o'zingiz oching"],
                ask=["Bu talab qaysi rasmiy kanalda ko'rinadi"],
                addressed_rule_ids=addressed_rule_ids(kwargs["user"]),
            ),
            input_tokens=10,
            output_tokens=5,
        )


def test_checkable_is_the_default_when_the_model_omits_the_field() -> None:
    # Fail-safe direction: a missing or garbled field must yield a real check.
    assert DraftOutput().situation_type is SituationType.checkable


def test_draft_schema_requires_situation_type_without_ref_indirection() -> None:
    schema = draft_output_schema()

    assert "situation_type" in schema["required"]
    assert schema["properties"]["situation_type"]["enum"] == ["checkable", "off_topic"]
    # Hosts that ignore $defs would silently drop the field and disable triage.
    assert "$defs" not in schema
    assert "$ref" not in json.dumps(schema)


async def test_off_topic_content_gets_the_fixed_redirect(session) -> None:
    llm = _OffTopicLLM()
    result = await run_check(
        CheckInput(
            user_key="off-topic-user",
            language=Language.ru,
            input_type=InputType.text,
            raw_text="какой сегодня день?",
        ),
        session=session,
        llm_provider=llm,
    )

    assert result.status == CheckStatus.off_topic
    assert llm.calls == 1
    assert result.rule_ids == []
    # Deterministic copy only — none of the model's prose reaches the user.
    assert result.text == format_status_message(CheckStatus.off_topic, Language.ru)
    assert result.check_id is not None


async def test_off_topic_redirect_consumes_a_daily_slot(session) -> None:
    # It costs a real model call, so it is billable: junk stays capped by the
    # daily limit instead of running through an unmetered path.
    await run_check(
        CheckInput(
            user_key="off-topic-quota",
            language=Language.ru,
            input_type=InputType.text,
            raw_text="какой сегодня день?",
        ),
        session=session,
        llm_provider=_OffTopicLLM(),
    )

    assert await repo.get_usage(session, user_key="off-topic-quota", scope="user") == 1


async def test_off_topic_reply_is_localized_per_language(session) -> None:
    result = await run_check(
        CheckInput(
            user_key="off-topic-uz",
            language=Language.uz_latn,
            input_type=InputType.text,
            raw_text="bugun qanday kun?",
        ),
        session=session,
        llm_provider=_OffTopicLLM(),
    )

    assert result.status == CheckStatus.off_topic
    assert result.language == Language.uz_latn
    assert result.text == format_status_message(CheckStatus.off_topic, Language.uz_latn)


async def test_rule_hit_overrides_an_off_topic_classification(session) -> None:
    # The safety-critical direction: a detected fact is authoritative evidence
    # that this IS a situation, so the model may not wave it off as chatter.
    llm = _MislabellingLLM()
    result = await run_check(
        CheckInput(
            user_key="off-topic-override",
            language=Language.uz_latn,
            input_type=InputType.text,
            raw_text=_SUSPICIOUS_MESSAGE,
        ),
        session=session,
        llm_provider=llm,
    )

    assert result.status == CheckStatus.ok
    assert result.rule_ids
    assert result.text != format_status_message(CheckStatus.off_topic, Language.uz_latn)
