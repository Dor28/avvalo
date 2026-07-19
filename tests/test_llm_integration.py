"""T6 LLM prompt/provider/cost integration tests."""

import json
import logging
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest
from openai import RateLimitError
from sqlalchemy import select

from app.config import Settings
from app.data.models import CheckEvent
from app.engine import CheckInput, CheckStatus, InputType, Language, run_check
from app.engine.llm import LLMProviderError, LLMResponse, OpenAICompatibleProvider
from app.engine.llm.prompt import build_prompt, draft_output_schema
from app.engine.minimize import minimize
from app.engine.rules import run_rules
from app.engine.types import DraftOutput
from app.obs.cost import estimate_llm_cost_usd
from tests.support import addressed_rule_ids


class CapturingLLMProvider:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def analyze(self, **kwargs) -> LLMResponse:
        self.calls.append(kwargs)
        return LLMResponse(
            draft=DraftOutput(
                red_flags=["The message asks for an SMS code."],
                pattern="Authority and urgency pressure.",
                verify=["Open the official bank app yourself."],
                ask=["Ask why an official channel cannot be used."],
                addressed_rule_ids=addressed_rule_ids(kwargs["user"]),
            ),
            input_tokens=1000,
            output_tokens=500,
        )


class FailingLLMProvider:
    async def analyze(self, **_kwargs) -> LLMResponse:
        raise LLMProviderError("boom")


class FakeCompletions:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "red_flags": ["One warning sign."],
                                "pattern": "Urgency.",
                                "verify": ["Check independently."],
                                "ask": ["Ask a control question."],
                            }
                        )
                    )
                )
            ],
            usage=SimpleNamespace(prompt_tokens=123, completion_tokens=45),
        )


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.completions = FakeCompletions()
        self.chat = SimpleNamespace(completions=self.completions)


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        telegram_token="token",
        database_url="postgresql+asyncpg://avvalo:avvalo@localhost:5432/avvalo",
        app_hmac_secret="test-hmac-secret",
        llm_base_url="http://localhost:11434/v1",
        llm_api_key="ollama",
        llm_model="qwen2.5:7b-instruct",
        llm_in_rate_per_m=2.0,
        llm_out_rate_per_m=6.0,
        web_session_secret="test-web-session-secret",
    )


def test_build_prompt_renders_rule_descriptions_and_minimized_content() -> None:
    raw_text = (
        "Bank xavfsizlik xizmatidanmiz. SMS kod 123456 ni yuboring. "
        "Tel: +998 90 123 45 67, karta 8600 1234 1234 5678."
    )
    hits, signals = run_rules(raw_text, "family")
    minimized = minimize(raw_text, signals)

    system, user = build_prompt(
        face_id="family",
        language=Language.uz_latn,
        minimized_text=minimized,
        rule_hits=hits,
        signals=signals,
    )

    assert "Return ONLY a JSON object" in system
    assert "{minimized_text}" not in user
    assert "fs.credential.otp" in user
    assert "Asks for an SMS" in user
    assert "[PHONE]" in user
    assert "[CARD]" in user
    assert "+998 90 123 45 67" not in user
    assert "8600 1234 1234 5678" not in user


async def test_openai_compatible_provider_maps_json_response() -> None:
    client = FakeOpenAIClient()
    provider = OpenAICompatibleProvider(
        base_url="http://localhost:11434/v1",
        api_key="ollama",
        model="qwen2.5:7b-instruct",
        client=client,
    )

    response = await provider.analyze(
        system="system",
        user="user",
        schema=draft_output_schema(),
        max_output_tokens=321,
    )

    call = client.completions.calls[0]
    assert call["model"] == "qwen2.5:7b-instruct"
    assert call["temperature"] == 0.2
    assert call["max_tokens"] == 321
    assert call["response_format"] == {"type": "json_object"}
    assert response.draft.red_flags == ["One warning sign."]
    assert response.input_tokens == 123
    assert response.output_tokens == 45


def test_estimate_llm_cost_usd() -> None:
    assert (
        estimate_llm_cost_usd(
            input_tokens=1000,
            output_tokens=500,
            in_rate_per_m=2.0,
            out_rate_per_m=6.0,
        )
        == 0.005
    )


async def test_pipeline_records_llm_usage_and_cost_without_content(session) -> None:
    provider = CapturingLLMProvider()
    raw_text = (
        "Bank xavfsizlik xizmatidanmiz. Hozir SMS kod 123456 ni yuboring. "
        "Tel: +998 90 123 45 67."
    )

    result = await run_check(
        CheckInput(
            face="family",
            user_key="u-llm",
            language=Language.uz_latn,
            input_type=InputType.text,
            raw_text=raw_text,
        ),
        session=session,
        llm_provider=provider,
        settings=_settings(),
    )
    await session.commit()

    assert result.status == CheckStatus.ok
    assert result.input_tokens == 1000
    assert result.output_tokens == 500
    assert result.cost_usd == 0.005
    assert provider.calls[0]["max_output_tokens"] == 600
    assert "123456" not in provider.calls[0]["user"]
    assert "+998 90 123 45 67" not in provider.calls[0]["user"]

    stored_event = (await session.execute(select(CheckEvent))).scalar_one()
    assert stored_event.input_tokens == 1000
    assert stored_event.output_tokens == 500
    assert stored_event.cost_usd == Decimal("0.005000")
    stored_values = [
        str(getattr(stored_event, column.name))
        for column in CheckEvent.__table__.columns
        if getattr(stored_event, column.name) is not None
    ]
    assert "123456" not in "".join(stored_values)
    assert "+998 90 123 45 67" not in "".join(stored_values)


async def test_openai_provider_classifies_api_status_errors() -> None:
    request = httpx.Request("POST", "https://openrouter.test/api/v1/chat/completions")
    response = httpx.Response(429, request=request, json={"error": {"message": "rate limited"}})

    class RaisingCompletions:
        async def create(self, **_kwargs):
            raise RateLimitError("Error code: 429 - rate limited", response=response, body=None)

    client = SimpleNamespace(chat=SimpleNamespace(completions=RaisingCompletions()))
    provider = OpenAICompatibleProvider(
        base_url="http://localhost:11434/v1",
        api_key="key",
        model="qwen2.5:7b-instruct",
        client=client,
    )

    with pytest.raises(LLMProviderError) as excinfo:
        await provider.analyze(
            system="system",
            user="user",
            schema=draft_output_schema(),
            max_output_tokens=10,
        )

    # The structured fields survive classification; the SDK message stays in args only.
    assert excinfo.value.error_code == "RateLimitError"
    assert excinfo.value.status_code == 429


async def test_pipeline_llm_error_logs_status_code_but_never_provider_text(caplog) -> None:
    caplog.set_level(logging.ERROR, logger="app.obs.events")

    class ClassifiedFailingProvider:
        async def analyze(self, **_kwargs) -> LLMResponse:
            raise LLMProviderError(
                "Error code: 429 - Rate limit exceeded: free-tier quota reset at midnight",
                error_code="RateLimitError",
                status_code=429,
            )

    result = await run_check(
        CheckInput(
            face="family",
            user_key="u-llm-429",
            language=Language.ru,
            input_type=InputType.text,
            raw_text="Мне позвонили и сказали, что из прокуратуры.",
        ),
        llm_provider=ClassifiedFailingProvider(),
    )

    assert result.status == CheckStatus.llm_error
    assert result.error_class == "RateLimitError"

    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "'error_type': 'RateLimitError'" in messages
    assert "'status_code': 429" in messages
    assert "free-tier quota" not in messages


async def test_pipeline_llm_error_keeps_deterministic_rule_ids(caplog) -> None:
    caplog.set_level(logging.ERROR, logger="app.obs.events")
    result = await run_check(
        CheckInput(
            face="family",
            user_key="u-llm-fail",
            language=Language.uz_latn,
            input_type=InputType.text,
            raw_text="Bank xavfsizlik xizmatidanmiz. SMS kodni yuboring.",
        ),
        llm_provider=FailingLLMProvider(),
    )

    assert result.status == CheckStatus.llm_error
    assert result.error_class == "LLMProviderError"
    assert "fs.credential.otp" in result.rule_ids

    # The technical error log carries the exception class, never str(exc) —
    # "boom" (FailingLLMProvider's message) must not reach logs.
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "event=app_error" in messages
    assert "'error_type': 'LLMProviderError'" in messages
    assert "boom" not in messages
    assert result.llm_ms is not None
