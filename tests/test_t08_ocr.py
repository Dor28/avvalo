"""T8 — OCR interface & provider selection (V1_TECHNICAL_PLAN §7).

Live acceptance specs that skip until the OCR providers land. The GCV/Tesseract
calls need credentials or binaries, so the offline-checkable contract is tested:
the OCRResult shape and the on-prem stub raising NotImplementedError.
"""

import inspect

import pytest

from app.config import Settings


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
