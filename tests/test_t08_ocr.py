"""T8 — OCR interface & provider selection (V1_TECHNICAL_PLAN §7).

Live acceptance specs that skip until the OCR providers land. The GCV/Tesseract
calls need credentials or binaries, so the offline-checkable contract is tested:
the OCRResult shape, the on-prem stub raising NotImplementedError, and how the
pipeline maps each OCR failure class to a user-facing status.
"""

import inspect
import logging

import pytest

from app.config import Settings
from app.engine import CheckInput, CheckStatus, InputType, Language, run_check
from app.engine.ocr import OCRInvalidImageError, OCRProviderError, OCRResult


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


def test_ocr_result_contract() -> None:
    from app.engine.ocr.base import OCRResult

    ocr_result = OCRResult
    fields = getattr(ocr_result, "model_fields", {})
    assert "text" in fields and "confidence" in fields


async def test_on_prem_stub_raises_not_implemented() -> None:
    stub = pytest.importorskip("app.engine.ocr.local_stub")
    providers = [
        value
        for value in vars(stub).values()
        if inspect.isclass(value) and hasattr(value, "extract")
    ]
    if not providers:
        pytest.skip("no OCR provider class in local_stub yet")

    try:
        provider = providers[0]()
    except Exception as exc:  # construction needs args we can't supply
        pytest.skip(f"cannot instantiate stub provider: {exc}")

    with pytest.raises(NotImplementedError):
        await provider.extract(b"\x89PNG\r\n")


class _FailingOCRProvider:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def extract(self, _image_bytes: bytes) -> OCRResult:
        raise self._exc


def _image_input(user_key: str) -> CheckInput:
    return CheckInput(
        face="family",
        user_key=user_key,
        language=Language.ru,
        input_type=InputType.image,
        image_bytes=b"\x89PNG\r\n",
    )


async def test_ocr_provider_outage_maps_to_ocr_error_with_cause_class(caplog) -> None:
    caplog.set_level(logging.ERROR, logger="app.obs.events")
    result = await run_check(
        _image_input("u-ocr-outage"),
        ocr_provider=_FailingOCRProvider(
            OCRProviderError(
                "vision said: quota exceeded for project scam-check",
                error_code="ServiceUnavailable",
            )
        ),
    )

    assert result.status == CheckStatus.ocr_error
    assert result.error_class == "ServiceUnavailable"

    # Logs carry the cause class only, never the provider's message.
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "'error_type': 'ServiceUnavailable'" in messages
    assert "quota exceeded" not in messages


async def test_unreadable_image_maps_to_unsupported_media() -> None:
    result = await run_check(
        _image_input("u-ocr-bad-image"),
        ocr_provider=_FailingOCRProvider(
            OCRInvalidImageError(
                "image bytes are not a readable image", error_code="UnidentifiedImageError"
            )
        ),
    )

    assert result.status == CheckStatus.unsupported_media
    assert result.error_class == "UnidentifiedImageError"


async def test_misconfigured_ocr_provider_maps_to_ocr_error(caplog) -> None:
    caplog.set_level(logging.ERROR, logger="app.obs.events")
    result = await run_check(
        _image_input("u-ocr-config"),
        settings=_settings(ocr_provider="bogus"),
    )

    assert result.status == CheckStatus.ocr_error
    assert result.error_class == "OCRConfigError"
    assert "'error_type': 'OCRConfigError'" in "\n".join(
        record.getMessage() for record in caplog.records
    )


def test_provider_selection_is_configurable(callable_or_skip) -> None:
    select = callable_or_skip(
        "app.engine.ocr", "get_provider", "get_ocr_provider", "build_provider", "provider_for"
    )
    provider = select(_settings(ocr_provider="local_stub"))
    assert provider.__class__.__name__ == "LocalStubOCRProvider"


def test_paddleocr_provider_selection(callable_or_skip) -> None:
    select = callable_or_skip(
        "app.engine.ocr", "get_provider", "get_ocr_provider", "build_provider", "provider_for"
    )
    provider = select(_settings(ocr_provider="paddleocr"))
    assert provider.__class__.__name__ == "PaddleOCRProvider"
