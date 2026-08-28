"""OCR boundary, preprocessing, provider selection, and pipeline failure tests."""

import logging
from io import BytesIO
from pathlib import Path

import pytest
import yaml
from PIL import Image

from app.config import Settings
from app.engine import CheckInput, CheckStatus, InputType, Language, run_check
from app.engine.ocr import (
    LocalStubOCRProvider,
    OCRInvalidImageError,
    OCRProviderError,
    OCRResult,
    PaddleOCRProvider,
    RapidOCRProvider,
    get_provider,
    reset_provider_cache,
    warmup_provider,
)
from app.engine.ocr.base import (
    MAX_IMAGE_DIMENSION,
    MAX_IMAGE_PIXELS,
    script_match_score,
    strip_image_metadata,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


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


def test_rapidocr_is_the_default_provider() -> None:
    """The default must work on a fresh checkout: no key, no network."""

    reset_provider_cache()

    assert isinstance(get_provider(_settings()), RapidOCRProvider)


def test_provider_is_reused_across_checks() -> None:
    """Rebuilding per check reloads the OCR models on every single image."""

    reset_provider_cache()
    settings = _settings(ocr_provider="rapidocr")
    first = get_provider(settings)

    assert get_provider(settings) is first

    reset_provider_cache()
    assert get_provider(settings) is not first


def test_provider_cache_keys_on_configuration() -> None:
    reset_provider_cache()
    rapid = get_provider(_settings(ocr_provider="rapidocr"))
    stub = get_provider(_settings(ocr_provider="local_stub"))

    assert rapid is not stub
    assert isinstance(stub, LocalStubOCRProvider)


def _png_bytes() -> bytes:
    payload = BytesIO()
    Image.new("RGB", (40, 20), "white").save(payload, format="PNG")
    return payload.getvalue()


async def test_rapidocr_prefers_the_script_that_recovered_more_text(monkeypatch) -> None:
    """A Latin model reading Cyrillic returns short, *confident* nonsense.

    Measured: on a rendered Russian screenshot the Latin model reported 0.90 on
    14 characters of garbage, so picking on confidence alone silently returned
    it and the Cyrillic model never ran.
    """

    provider = RapidOCRProvider()
    attempts = {
        "latin": OCRResult(text="Baa\n15\nMHyT", confidence=0.90),
        "cyrillic": OCRResult(
            text="Ваша карта заблокирована.\nСрочно подтвердите код 4821",
            confidence=0.88,
        ),
    }
    monkeypatch.setattr(provider, "_run_engine", lambda script, image: attempts[script])

    result = await provider.extract(_png_bytes())

    assert result.text.startswith("Ваша")
    assert result.confidence == 0.88


async def test_rapidocr_still_prefers_higher_confidence_at_equal_length(monkeypatch) -> None:
    provider = RapidOCRProvider()
    attempts = {
        "latin": OCRResult(text="Kartani tasdiqlang", confidence=0.95),
        "cyrillic": OCRResult(text="Kaptahn tacdnqlang", confidence=0.61),
    }
    monkeypatch.setattr(provider, "_run_engine", lambda script, image: attempts[script])

    result = await provider.extract(_png_bytes())

    assert result.text == "Kartani tasdiqlang"


def test_script_match_score_weighs_recovered_characters() -> None:
    confident_garbage = OCRResult(text="Baa 15", confidence=0.99)
    full_read = OCRResult(text="Ваша карта заблокирована сегодня", confidence=0.70)

    assert script_match_score(full_read) > script_match_score(confident_garbage)


def test_rapidocr_covers_both_scripts_avvalo_accepts() -> None:
    """Uzbek Latin and Cyrillic input need different PP-OCRv5 models."""

    assert RapidOCRProvider().scripts == ("latin", "cyrillic")


async def test_warmup_is_optional_for_providers_without_startup_cost() -> None:
    reset_provider_cache()

    await warmup_provider(_settings(ocr_provider="local_stub"))


async def test_paddleocr_warmup_loads_every_configured_language(monkeypatch) -> None:
    provider = PaddleOCRProvider(langs=("uz", "ru"))
    built: list[str] = []
    monkeypatch.setattr(provider, "_engine", built.append)

    await provider.warmup()

    assert built == ["uz", "ru"]


async def test_rapidocr_warmup_loads_every_configured_script(monkeypatch) -> None:
    provider = RapidOCRProvider()
    built: list[str] = []
    probed: list[str] = []

    def engine(script: str):
        built.append(script)
        return lambda image: probed.append(script)

    monkeypatch.setattr(provider, "_engine", engine)
    await provider.warmup()

    assert built == ["latin", "cyrillic"]
    # The probe pass is what forces lazily fetched artifacts into the image.
    assert probed == ["latin", "cyrillic"]


async def test_rapidocr_warmup_surfaces_a_missing_model(monkeypatch) -> None:
    """A build that cannot fetch models must fail loudly, not silently."""

    provider = RapidOCRProvider()
    monkeypatch.setattr(
        provider, "_engine", lambda script: (_ for _ in ()).throw(FileNotFoundError(script))
    )

    with pytest.raises(FileNotFoundError):
        await provider.warmup()


def test_ocr_models_are_baked_into_the_image() -> None:
    """A read-only container cannot download models, so the build must.

    The previous provider fetched weights on first use and wrote them under
    ``$HOME``, which ``read_only: true`` forbids — every image check failed
    with ``ocr_error``. Baking the models in removes the writable directory and
    the runtime network call together.
    """

    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = yaml.safe_load(
        (REPO_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    )

    assert compose["services"]["app"]["read_only"] is True
    assert "RapidOCRProvider().warmup()" in dockerfile
    # Warmup must run after the app package is installed, or it cannot import.
    assert dockerfile.index("pip install --require-hashes") < dockerfile.index("warmup()")


def test_runtime_image_uses_headless_opencv() -> None:
    """rapidocr imports cv2, and opencv-python links X11 that slim lacks."""

    runtime_lock = (REPO_ROOT / "requirements.lock").read_text(encoding="utf-8")
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "\nopencv-python-headless==" in runtime_lock
    # Both wheels install the same `cv2`, so the X11-linked one is kept out by a
    # marker that is never true rather than by being absent from the closure.
    assert "sys_platform == 'never'" in runtime_lock
    # ...which only holds if pip installs the lock instead of re-resolving it.
    assert "--require-hashes --no-deps" in dockerfile


def test_runtime_image_excludes_the_paddle_dependency_tree() -> None:
    """paddlepaddle and paddlex dominate image size and memory; keep them out."""

    runtime_lock = (REPO_ROOT / "requirements.lock").read_text(encoding="utf-8")
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "\npaddlepaddle==" not in runtime_lock
    assert "\npaddlex==" not in runtime_lock
    assert "\nrapidocr==" in runtime_lock
    assert "\nonnxruntime==" in runtime_lock
    # Still installable for accuracy comparisons, just not in the image.
    assert "paddle = [" in pyproject
