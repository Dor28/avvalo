"""Verbatim composition of reviewed card wording (PIPELINE_V2 §4)."""

from app.engine import CheckInput, CheckStatus, InputType, Language, run_check
from app.engine.knowledge import (
    KnowledgeBase,
    KnowledgeCard,
    LocalizedCardText,
    compose_card_text,
    retrieve_knowledge,
)
from app.engine.llm import LLMResponse
from app.engine.types import DraftOutput, Evidence, RuleHit, Signal

_UZ_FLAG = "Sizdan bir martalik SMS kod so'ralmoqda."
_UZ_VERIFY = "Suhbatni to'xtating va bank ilovasini o'zingiz oching."
_UZ_QUESTION = "Bu ma'lumot nega rasmiy ilovadan tashqarida kerak?"


def _card(card_id: str = "family.credential_theft", *, localized: bool = True) -> KnowledgeCard:
    return KnowledgeCard(
        id=card_id,
        version="1.0.0",
        status="approved",
        reviewer="test",
        trigger_rule_ids=["fs.credential.otp"],
        trigger_signal_kinds=["otp_request"],
        mechanism="The sender asks for authentication secrets in an ordinary chat.",
        red_flags=["A one-time code is requested."],
        verify_steps=["Open the official app independently."],
        questions=["Why is this needed outside the official app?"],
        localized=(
            {
                "uz_latn": LocalizedCardText(
                    red_flags=[_UZ_FLAG],
                    verify_steps=[_UZ_VERIFY],
                    questions=[_UZ_QUESTION],
                )
            }
            if localized
            else {}
        ),
    )


def _draft(**overrides) -> DraftOutput:
    base = {
        "red_flags": [Evidence(text="Model wording.", source_id="fs.credential.otp")],
        "pattern": "Authority pressure.",
        "verify": ["Model verification step."],
        "ask": ["Model question?"],
        "addressed_rule_ids": ["fs.credential.otp"],
    }
    return DraftOutput(**{**base, **overrides})


def test_mandatory_card_wording_is_emitted_verbatim() -> None:
    composed = compose_card_text(
        _draft(),
        [_card()],
        mandatory_card_ids=["family.credential_theft"],
        language=Language.uz_latn,
    )

    assert composed.red_flags[0] == Evidence(text=_UZ_FLAG, source_id="family.credential_theft")
    assert composed.verify[0] == _UZ_VERIFY
    assert composed.ask[0] == _UZ_QUESTION


def test_reviewed_wording_is_ordered_ahead_of_model_wording() -> None:
    """Blocks truncate to three, so order decides which survives."""

    composed = compose_card_text(
        _draft(),
        [_card()],
        mandatory_card_ids=["family.credential_theft"],
        language=Language.uz_latn,
    )

    assert [flag.text for flag in composed.red_flags] == [_UZ_FLAG, "Model wording."]
    assert composed.verify == [_UZ_VERIFY, "Model verification step."]


def test_a_cue_or_router_card_never_composes() -> None:
    """An alias/router match is a relevance guess, not detected evidence."""

    composed = compose_card_text(
        _draft(),
        [_card()],
        mandatory_card_ids=[],
        language=Language.uz_latn,
    )

    assert [flag.text for flag in composed.red_flags] == ["Model wording."]
    assert composed.verify == ["Model verification step."]


def test_a_card_without_review_in_this_language_falls_back_to_the_model() -> None:
    composed = compose_card_text(
        _draft(),
        [_card()],
        mandatory_card_ids=["family.credential_theft"],
        language=Language.ru,
    )

    assert [flag.text for flag in composed.red_flags] == ["Model wording."]


def test_an_untranslated_card_changes_nothing() -> None:
    draft = _draft()

    composed = compose_card_text(
        draft,
        [_card(localized=False)],
        mandatory_card_ids=["family.credential_theft"],
        language=Language.uz_latn,
    )

    assert composed is draft


def test_a_model_echo_of_composed_wording_is_not_duplicated() -> None:
    composed = compose_card_text(
        _draft(
            red_flags=[
                Evidence(text=f"  {_UZ_FLAG.upper()}  ", source_id="fs.credential.otp"),
                Evidence(text="Distinct extra warning.", source_id="fs.credential.otp"),
            ],
            verify=[_UZ_VERIFY],
        ),
        [_card()],
        mandatory_card_ids=["family.credential_theft"],
        language=Language.uz_latn,
    )

    assert [flag.text for flag in composed.red_flags] == [_UZ_FLAG, "Distinct extra warning."]
    assert composed.verify == [_UZ_VERIFY]


async def test_retrieval_reports_which_cards_were_rule_or_signal_triggered() -> None:
    class _Store:
        def load(self) -> KnowledgeBase:
            return KnowledgeBase(version="test-1", cards=(_card(),))

    result = await retrieve_knowledge(
        minimized_text="kodni yuboring",
        rule_hits=[
            RuleHit(
                rule_id="fs.credential.otp",
                family="credential_theft",
                message_key="otp",
                severity=3,
            )
        ],
        signals=[],
        store=_Store(),
    )

    assert result.mandatory_card_ids == ("family.credential_theft",)


async def test_a_signal_triggered_card_is_mandatory_too() -> None:
    class _Store:
        def load(self) -> KnowledgeBase:
            return KnowledgeBase(version="test-1", cards=(_card(),))

    result = await retrieve_knowledge(
        minimized_text="no keywords here",
        rule_hits=[],
        signals=[Signal(kind="otp_request")],
        store=_Store(),
    )

    assert result.mandatory_card_ids == ("family.credential_theft",)


class _FakeLLM:
    def __init__(self, draft: DraftOutput) -> None:
        self.draft = draft

    async def analyze(self, **kwargs) -> LLMResponse:
        return LLMResponse(draft=self.draft, input_tokens=10, output_tokens=5)


async def test_composed_wording_reaches_the_user_through_the_pipeline(session) -> None:
    class _Store:
        def load(self) -> KnowledgeBase:
            return KnowledgeBase(version="test-1", cards=(_card(),))

    result = await run_check(
        CheckInput(
            user_key="compose-user",
            language=Language.uz_latn,
            input_type=InputType.text,
            raw_text="Bank xizmatidanmiz. SMS orqali kelgan 6 xonali kodni yuboring.",
        ),
        session=session,
        llm_provider=_FakeLLM(_draft()),
        knowledge_store=_Store(),
    )
    await session.commit()

    assert result.status is CheckStatus.ok
    assert _UZ_FLAG in (result.text or "")
    # The card id is internal and must never surface in the reply.
    assert "family.credential_theft" not in (result.text or "")


async def test_composed_wording_still_faces_the_safety_validator(session) -> None:
    """A card is reviewed, not trusted: composed text is not a bypass."""

    unsafe = _card()
    unsafe = unsafe.model_copy(
        update={
            "localized": {
                "uz_latn": LocalizedCardText(
                    red_flags=["Bu xabar firibgarlik."],
                    verify_steps=[_UZ_VERIFY],
                    questions=[_UZ_QUESTION],
                )
            }
        }
    )

    class _Store:
        def load(self) -> KnowledgeBase:
            return KnowledgeBase(version="test-1", cards=(unsafe,))

    result = await run_check(
        CheckInput(
            user_key="compose-unsafe",
            language=Language.uz_latn,
            input_type=InputType.text,
            raw_text="Bank xizmatidanmiz. SMS orqali kelgan 6 xonali kodni yuboring.",
        ),
        session=session,
        llm_provider=_FakeLLM(_draft()),
        knowledge_store=_Store(),
    )
    await session.commit()

    # "firibgarlik" is a banned verdict word; the draft must not ship as written.
    assert "firibgarlik" not in (result.text or "")
    assert result.status is CheckStatus.safety_fallback
