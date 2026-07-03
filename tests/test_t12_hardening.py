"""T12 - hardening: provider timeouts and graceful failure."""

import asyncio

from app.config import Settings
from app.engine import CheckInput, CheckStatus, InputType, Language, run_check
from app.engine.ocr import OCRResult


class SlowLLMProvider:
    async def analyze(self, **_kwargs):
        await asyncio.sleep(0.05)
        raise AssertionError("timeout should fire before this provider returns")


class SlowOCRProvider:
    async def extract(self, _image_bytes: bytes) -> OCRResult:
        await asyncio.sleep(0.05)
        return OCRResult(text="Bank xavfsizlik xizmati SMS kodni so'radi", confidence=0.9)


def _settings(**overrides) -> Settings:
    values = {
        "telegram_token": "token",
        "database_url": "postgresql+asyncpg://avvalo:avvalo@localhost:5432/avvalo",
        "app_hmac_secret": "test-hmac-secret",
        "llm_base_url": "http://localhost:11434/v1",
        "llm_api_key": "ollama",
        "llm_model": "qwen2.5:7b-instruct",
        "web_session_secret": "test-web-session-secret",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_timeout_status_is_part_of_the_contract() -> None:
    assert CheckStatus.timeout.value == "timeout"


def test_pipeline_has_a_timeout_wrapper() -> None:
    from app.engine.pipeline import _with_timeout

    assert callable(_with_timeout)


async def test_llm_timeout_returns_timeout_without_safety_conclusion() -> None:
    result = await run_check(
        CheckInput(
            face="family",
            user_key="timeout-user",
            language=Language.uz_latn,
            input_type=InputType.text,
            raw_text="Bank xavfsizlik xizmatidanmiz. SMS kodni yuboring.",
        ),
        llm_provider=SlowLLMProvider(),
        settings=_settings(llm_timeout_s=0.001),
    )

    assert result.status == CheckStatus.timeout
    assert result.error_class == "TimeoutError"
    assert not result.safety_blocked
    assert result.rule_ids


async def test_ocr_timeout_returns_timeout_before_llm_call() -> None:
    result = await run_check(
        CheckInput(
            face="family",
            user_key="ocr-timeout-user",
            language=Language.uz_latn,
            input_type=InputType.image,
            image_bytes=b"not-empty",
        ),
        ocr_provider=SlowOCRProvider(),
        llm_provider=SlowLLMProvider(),
        settings=_settings(ocr_timeout_s=0.001, llm_timeout_s=0.001),
    )

    assert result.status == CheckStatus.timeout
    assert result.error_class == "TimeoutError"
    assert result.ocr_ms is not None
