"""OCR boundary, preprocessing, provider selection, and pipeline failure tests."""

import inspect
import logging
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app.config import Settings
from app.engine import CheckInput, CheckStatus, InputType, Language, run_check
from app.engine.ocr import (
    LocalStubOCRProvider,
    OCRInvalidImageError,
    OCRProviderError,
    OCRResult,
    PaddleOCRProvider,
    check_ocr_provider,
    get_provider,
    probe_image,
    warmup,
)
from app.engine.ocr.base import MAX_IMAGE_DIMENSION, MAX_IMAGE_PIXELS, strip_image_metadata


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


def test_image_preprocessing_rejects_excessive_pixel_count() -> None:
    side = int(MAX_IMAGE_PIXELS**0.5) + 1
    image = Image.new("1", (side, side))
    payload = BytesIO()
    image.save(payload, format="PNG")

    with pytest.raises(OCRInvalidImageError) as exc_info:
        strip_image_metadata(payload.getvalue())

    assert exc_info.value.error_code == "ImagePixelLimitExceeded"


def test_image_preprocessing_rejects_excessive_dimension() -> None:
    image = Image.new("1", (MAX_IMAGE_DIMENSION + 1, 1))
    payload = BytesIO()
    image.save(payload, format="PNG")

    with pytest.raises(OCRInvalidImageError) as exc_info:
        strip_image_metadata(payload.getvalue())

    assert exc_info.value.error_code == "ImageDimensionLimitExceeded"


async def test_on_prem_stub_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        await LocalStubOCRProvider().extract(b"\x89PNG\r\n")


class _FailingOCRProvider:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def extract(self, _image_bytes: bytes) -> OCRResult:
        raise self._exc


def _image_input(user_key: str) -> CheckInput:
    return CheckInput(
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


def test_provider_selection_is_configurable() -> None:
    provider = get_provider(_settings(ocr_provider="local_stub"))
    assert isinstance(provider, LocalStubOCRProvider)


def test_paddleocr_provider_selection() -> None:
    provider = get_provider(_settings(ocr_provider="paddleocr"))
    assert isinstance(provider, PaddleOCRProvider)


async def test_preflight_rejects_an_unsupported_provider() -> None:
    with pytest.raises(ValueError):
        await check_ocr_provider(_settings(ocr_provider="bogus"))


async def test_preflight_rejects_a_provider_that_cannot_read_an_image() -> None:
    """The stub answers config checks but cannot OCR, so startup must not pass."""

    with pytest.raises(NotImplementedError):
        await check_ocr_provider(_settings(ocr_provider="local_stub"))


def test_preflight_probe_image_is_generated_not_user_content() -> None:
    assert probe_image().startswith(b"\x89PNG")


def test_paddleocr_warmup_covers_every_language_the_provider_uses() -> None:
    """PaddleOCR downloads an uncached model on first use, and production runs
    read-only — so a language the build never warmed becomes a live ocr_error."""

    warmed = inspect.signature(warmup.main).parameters["langs"].default

    assert warmed == PaddleOCRProvider().langs


def test_dockerfile_bakes_paddleocr_weights_at_a_pinned_cache_path() -> None:
    """paddlex reads PADDLE_PDX_CACHE_HOME into a module constant at import, so
    the build and the runtime must agree on an absolute path that ignores HOME."""

    dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text(encoding="utf-8")

    assert "PADDLE_PDX_CACHE_HOME=/opt/paddlex" in dockerfile
    assert "python -m app.engine.ocr.warmup" in dockerfile
