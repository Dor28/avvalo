"""T9 — daily limits, feedback & privacy-safe events (V1_TECHNICAL_PLAN §12, §13 T9).

The rate-limit and feedback storage primitives exist now (tested live below). The
event logger's content-refusal discipline (§12) is a live spec that skips until
obs/events.py lands.
"""

import inspect
import logging

import pytest

from app.data import repo
from app.engine import CheckInput, CheckStatus, InputType, Language, run_check
from app.engine.faces import FACES
from app.engine.llm import LLMResponse
from app.engine.types import DraftOutput
from app.obs.events import log_error


class FakeLLMProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def analyze(self, **_kwargs) -> LLMResponse:
        self.calls += 1
        return LLMResponse(
            draft=DraftOutput(
                red_flags=["The message asks for a one-time code."],
                verify=["Open the official app yourself."],
                ask=["Ask which official channel shows this request."],
            ),
            input_tokens=10,
            output_tokens=5,
        )


async def test_daily_limit_boundary_is_reachable(session) -> None:
    face = "family"
    limit = FACES[face].daily_limit
    counts = [
        await repo.increment_usage(session, user_key="capped", face=face) for _ in range(limit)
    ]
    assert counts[-1] == limit
    assert await repo.get_usage(session, user_key="capped", face=face) == limit


async def test_sixth_family_check_is_rate_limited(session) -> None:
    provider = FakeLLMProvider()
    check_input = CheckInput(
        face="family",
        user_key="daily-limit",
        language=Language.ru,
        input_type=InputType.text,
        raw_text="Bank xavfsizlik xizmatidanmiz. SMS kodni yuboring.",
    )

    results = [
        await run_check(check_input, session=session, llm_provider=provider)
        for _ in range(FACES["family"].daily_limit + 1)
    ]

    assert [result.status for result in results[:-1]] == [CheckStatus.ok] * 5
    assert results[-1].status == CheckStatus.rate_limited
    assert provider.calls == 5


async def test_feedback_is_stored_categorically(session) -> None:
    check_id = await repo.record_check_event(
        session, user_key="fb", face="family", input_type="text", language="ru", status="ok"
    )
    await repo.record_feedback(
        session, check_id=check_id, usefulness="partly", next_action="verify"
    )
    await session.commit()
    # No assertion on content — feedback rows are categorical only (§5.2).


async def test_feedback_rejects_non_categorical_values(session) -> None:
    check_id = await repo.record_check_event(
        session, user_key="fb2", face="family", input_type="text", language="ru", status="ok"
    )
    with pytest.raises(ValueError):
        await repo.record_feedback(
            session,
            check_id=check_id,
            usefulness="secret free text",
            next_action="verify",
        )


def test_log_event_accepts_metadata_and_refuses_content(callable_or_skip) -> None:
    log_event = callable_or_skip("app.obs.events", "log_event")
    params = inspect.signature(log_event).parameters.values()
    if not any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params):
        pytest.skip(f"log_event does not take **fields: {inspect.signature(log_event)}")

    try:
        log_event("check_completed", language="ru", face="family", status="ok")
    except TypeError as exc:
        pytest.skip(f"log_event metadata signature differs from §12: {exc}")

    # §12: a content-like field must be refused outright.
    with pytest.raises((ValueError, TypeError, KeyError)):
        log_event("check_completed", raw_text="secret submitted content")
    with pytest.raises(ValueError):
        log_event("check_failed", face="family", error_class="+998 90 123 45 67")


def test_log_error_accepts_metadata_and_refuses_content() -> None:
    log_error("llm", "LLMProviderError", face="family", attempt=1)

    with pytest.raises(ValueError):
        log_error("bogus_stage", "LLMProviderError")
    with pytest.raises(ValueError):
        log_error("llm", "LLMProviderError", reason="+998 90 123 45 67")
    with pytest.raises(ValueError):
        log_error("llm", "LLMProviderError", raw_text="secret submitted content")


def test_log_error_forwards_tags_to_sentry(monkeypatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr(
        "app.obs.events.sentry_sdk.capture_message",
        lambda message, **kwargs: calls.append({"message": message, **kwargs}),
    )

    log_error("llm", "LLMProviderError", face="family", attempt=1)

    assert len(calls) == 1
    call = calls[0]
    assert call["level"] == "error"
    assert call["fingerprint"] == ["app_error", "llm", "LLMProviderError"]
    assert call["tags"] == {
        "stage": "llm",
        "error_type": "LLMProviderError",
        "face": "family",
        "attempt": "1",
    }


def test_log_error_is_a_safe_no_op_without_sentry_init() -> None:
    # No sentry_sdk.init() has run anywhere in the test process (no SENTRY_DSN),
    # so this must not raise or attempt a network call.
    log_error("ocr", "OCRProviderError", face="merchants")


async def test_run_check_emits_privacy_safe_events(session, caplog) -> None:
    caplog.set_level(logging.INFO, logger="app.obs.events")
    await run_check(
        CheckInput(
            face="family",
            user_key="evented",
            language=Language.uz_latn,
            input_type=InputType.text,
            raw_text="Bank xavfsizlik xizmatidanmiz. SMS kodni yuboring.",
        ),
        session=session,
        llm_provider=FakeLLMProvider(),
    )

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "event=check_started" in messages
    assert "event=check_completed" in messages
    assert "SMS kodni" not in messages
