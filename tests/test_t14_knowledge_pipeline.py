"""T14 / R0 — knowledge retrieval and grounding acceptance tests.

The numbered tests map directly to docs/AI_KNOWLEDGE_PIPELINE.md §7.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from sqlalchemy import select

from app.data.models import CheckEvent
from app.engine import CheckInput, CheckStatus, InputType, Language, run_check
from app.engine.knowledge import (
    FileKnowledgeStore,
    KnowledgeBase,
    KnowledgeLookupError,
    retrieve_knowledge,
)
from app.engine.llm import LLMProviderError, LLMResponse
from app.engine.types import DraftOutput
from app.engine.validate import validate

REPO_ROOT = Path(__file__).resolve().parents[1]


class RecordingLLMProvider:
    """Return queued drafts or failures and retain the exact provider inputs."""

    def __init__(self, *outcomes: DraftOutput | Exception) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, object]] = []

    async def analyze(self, **kwargs) -> LLMResponse:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return LLMResponse(draft=outcome, input_tokens=20, output_tokens=10)


class UnavailableKnowledgeStore:
    """Simulate a missing or unreadable deploy-time knowledge pack."""

    def load(self, face_id: str) -> KnowledgeBase:
        raise KnowledgeLookupError(f"{face_id} knowledge is unavailable")


class InventingRouter:
    """Return an ID outside the backend-provided allowlist."""

    def __init__(self) -> None:
        self.allowed_ids: tuple[str, ...] = ()
        self.minimized_text: str | None = None

    async def route(
        self,
        *,
        face_id: str,
        minimized_text: str,
        allowed_ids: tuple[str, ...],
        max_results: int,
    ) -> list[str]:
        assert face_id == "family"
        assert max_results == 3
        self.allowed_ids = allowed_ids
        self.minimized_text = minimized_text
        return ["family.router_invention"]


def _check_input(raw_text: str, *, user_key: str) -> CheckInput:
    return CheckInput(
        face="family",
        user_key=user_key,
        language=Language.ru,
        input_type=InputType.text,
        raw_text=raw_text,
    )


def _useful_no_signal_draft() -> DraftOutput:
    return DraftOutput(
        red_flags=[],
        pattern=None,
        verify=["Check the written details through an independent source."],
        ask=["What details can be confirmed before deciding?"],
    )


async def test_r0_criterion_01_zero_rule_message_still_reaches_answer_llm() -> None:
    red_flag = "The other side changed the meeting place twice without explaining why."
    provider = RecordingLLMProvider(
        DraftOutput(
            red_flags=[red_flag],
            pattern="The story changes without an explanation.",
            verify=["Confirm the meeting details through an independent contact."],
            ask=["Why did the meeting place change twice?"],
        )
    )

    result = await run_check(
        _check_input(red_flag, user_key="r0-zero-rule"),
        llm_provider=provider,
    )

    assert result.rule_ids == []
    assert result.status == CheckStatus.ok
    assert result.no_signal is False
    assert red_flag in (result.text or "")
    assert len(provider.calls) == 1
    assert "- (none detected)" in str(provider.calls[0]["user"])


async def test_r0_criterion_02_authority_cue_retrieves_without_becoming_proof() -> None:
    provider = RecordingLLMProvider(
        DraftOutput(
            red_flags=[],
            pattern=None,
            verify=["Завершите звонок и найдите официальный канал самостоятельно."],
            ask=["Какой официальный номер дела можно проверить независимо?"],
        )
    )

    result = await run_check(
        _check_input(
            "Мне позвонили и сказали, что из прокуратуры.",
            user_key="r0-authority-cue",
        ),
        llm_provider=provider,
    )

    assert result.rule_ids == []
    assert result.knowledge_card_ids == ["family.authority_impersonation"]
    assert result.retrieval_mode == "cue"
    assert result.retrieval_status == "ok"
    assert result.status == CheckStatus.no_signal
    assert result.no_signal is True
    assert "family.authority_impersonation" in str(provider.calls[0]["user"])


async def test_r0_criterion_03_mandatory_cards_and_rule_facts_survive() -> None:
    red_flags = [
        "A one-time code is requested in the conversation.",
        "The message demands action immediately.",
        "The bank role is claimed only inside the message.",
    ]
    provider = RecordingLLMProvider(
        DraftOutput(
            red_flags=red_flags,
            pattern="Authority and time pressure are used together.",
            verify=["Open the bank app independently and check for a real notice."],
            ask=["Why must a code be shared outside the bank app?"],
            addressed_rule_ids=[
                "fs.authority.impersonation",
                "fs.credential.otp",
                "fs.urgency.deadline",
            ],
        )
    )
    raw_text = (
        "Bank xavfsizlik xizmatidanmiz. Kartangiz bloklanadi. "
        "Hozir SMS orqali kelgan 6 xonali kodni yuboring."
    )

    result = await run_check(
        _check_input(raw_text, user_key="r0-mandatory-cards"),
        llm_provider=provider,
    )

    expected_rules = {
        "fs.authority.impersonation",
        "fs.credential.otp",
        "fs.urgency.deadline",
    }
    expected_cards = {
        "family.authority_impersonation",
        "family.credential_theft",
        "family.urgency_secrecy",
    }
    assert set(result.rule_ids) == expected_rules
    assert set(result.knowledge_card_ids) == expected_cards
    assert result.retrieval_mode == "rule"
    prompt = str(provider.calls[0]["user"])
    assert all(rule_id in prompt for rule_id in expected_rules)
    assert all(card_id in prompt for card_id in expected_cards)
    assert all(red_flag in (result.text or "") for red_flag in red_flags)


async def test_r0_criterion_04_no_match_still_returns_useful_non_verdict_answer() -> None:
    provider = RecordingLLMProvider(_useful_no_signal_draft())

    result = await run_check(
        _check_input(
            "I received a note about a meeting next week.",
            user_key="r0-no-match",
        ),
        llm_provider=provider,
    )

    assert result.status == CheckStatus.no_signal
    assert result.knowledge_card_ids == []
    assert result.retrieval_mode == "none"
    assert result.retrieval_status == "empty"
    assert "Check the written details" in (result.text or "")
    assert "safe" not in (result.text or "").casefold()


async def test_r0_criterion_05_router_cannot_inject_a_disallowed_card_id() -> None:
    router = InventingRouter()

    retrieval = await retrieve_knowledge(
        face_id="family",
        minimized_text="A wording with no deterministic knowledge cue.",
        rule_hits=[],
        signals=[],
        router=router,
    )

    assert "family.router_invention" not in router.allowed_ids
    assert router.minimized_text == "A wording with no deterministic knowledge cue."
    assert retrieval.cards == ()
    assert retrieval.knowledge_card_ids == []
    assert retrieval.invalid_router_ids == ("family.router_invention",)
    assert retrieval.status == "empty"
    assert retrieval.router_status == "invalid_ids"


async def test_r0_criterion_06_lookup_failure_degrades_without_fabrication() -> None:
    provider = RecordingLLMProvider(
        DraftOutput(
            red_flags=["The explanation changes inside the submitted text."],
            pattern="The explanation is inconsistent.",
            verify=["Confirm the details through an independent source."],
            ask=["Why did the explanation change?"],
        )
    )

    result = await run_check(
        _check_input(
            "The explanation changed after I asked for written details.",
            user_key="r0-lookup-unavailable",
        ),
        llm_provider=provider,
        knowledge_store=UnavailableKnowledgeStore(),
    )

    assert result.status == CheckStatus.ok
    assert result.retrieval_status == "unavailable"
    assert result.kb_version is None
    assert result.knowledge_card_ids == []
    assert "- (none selected)" in str(provider.calls[0]["user"])


async def test_r0_criterion_07_provider_failure_uses_fallback_not_no_signal() -> None:
    primary = RecordingLLMProvider(
        LLMProviderError(
            "provider response text must stay private",
            error_code="RateLimitError",
            status_code=429,
        )
    )
    fallback = RecordingLLMProvider(
        DraftOutput(
            red_flags=["The submitted story changes without an explanation."],
            pattern="The explanation is inconsistent.",
            verify=["Confirm the details through an independent source."],
            ask=["Why did the explanation change?"],
        )
    )

    result = await run_check(
        _check_input(
            "The submitted story changed after I asked for details.",
            user_key="r0-provider-fallback",
        ),
        llm_provider=primary,
        fallback_llm_provider=fallback,
    )

    assert len(primary.calls) == 1
    assert len(fallback.calls) == 1
    assert result.status == CheckStatus.ok
    assert result.no_signal is False
    assert result.error_class is None


@pytest.mark.parametrize(
    ("unsafe_text", "expected_reason"),
    [
        ("This person is a fraudster.", "banned verdict word"),
        (
            "The same reviewed case proves this person did it.",
            "reviewed case represented as proof",
        ),
        (
            "Use internal card family.authority_impersonation.",
            "internal knowledge id leaked",
        ),
        (
            "I checked the external database.",
            "unsupported external lookup claim",
        ),
    ],
)
def test_r0_criterion_08_retrieved_cases_cannot_create_verdicts_or_proof(
    unsafe_text: str,
    expected_reason: str,
) -> None:
    validation = validate(
        DraftOutput(
            red_flags=[unsafe_text],
            verify=["Use an independent official channel."],
            ask=["What can be confirmed independently?"],
        ),
        signals=[],
        rule_hits=[],
        language=Language.ru,
        knowledge_card_ids=["family.authority_impersonation"],
    )

    assert validation.ok is False
    assert validation.reason is not None
    assert expected_reason in validation.reason


async def test_r0_criterion_09_logs_and_db_keep_only_allowlisted_metadata(
    session,
    caplog,
) -> None:
    caplog.set_level(logging.INFO, logger="app.obs.events")
    raw_text = (
        "Мне позвонили и сказали, что из прокуратуры. "
        "Просили перезвонить на +998 90 123 45 67."
    )
    model_output = "The official role is claimed only inside this private call."
    provider = RecordingLLMProvider(
        DraftOutput(
            red_flags=[model_output],
            pattern="The caller invokes authority.",
            verify=["End the call and find the official channel independently."],
            ask=["What reference can be checked through that official channel?"],
        )
    )

    result = await run_check(
        _check_input(raw_text, user_key="r0-private-metadata"),
        session=session,
        llm_provider=provider,
    )
    await session.commit()

    event = (await session.execute(select(CheckEvent))).scalar_one()
    assert event.knowledge_card_ids == ["family.authority_impersonation"]
    assert event.reviewed_case_ids == []
    assert event.retrieval_mode == "cue"
    assert event.retrieval_status == "ok"
    assert event.kb_version == "2026-07-15-v1"
    assert result.kb_version == event.kb_version

    stored_values = "\n".join(
        str(getattr(event, column.name))
        for column in CheckEvent.__table__.columns
        if getattr(event, column.name) is not None
    )
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert raw_text not in stored_values
    assert raw_text not in messages
    assert "+998 90 123 45 67" not in stored_values
    assert "+998 90 123 45 67" not in messages
    assert model_output not in stored_values
    assert model_output not in messages
    assert "family.authority_impersonation" in messages
    assert "2026-07-15-v1" in messages


def test_r0_criterion_10_telegram_and_web_share_run_check() -> None:
    telegram = (REPO_ROOT / "app" / "bot" / "handlers.py").read_text(encoding="utf-8")
    web = (REPO_ROOT / "app" / "web" / "routes.py").read_text(encoding="utf-8")

    assert "result = await run_check(" in telegram
    assert "result = await run_check(" in web
    assert "from app.engine import" in telegram
    assert "from app.engine import" in web


def test_t14_deployed_knowledge_packs_are_loadable_and_copied_into_image() -> None:
    store = FileKnowledgeStore()
    family = store.load("family")

    assert family.version == "2026-07-15-v1"
    assert family.face == "family"
    assert len(family.cards) == 10
    assert all(card.status == "approved" for card in family.cards)

    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    ignored = {
        line.strip()
        for line in (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    assert "COPY knowledge ./knowledge" in dockerfile
    assert "knowledge" not in ignored
    assert "knowledge/" not in ignored
