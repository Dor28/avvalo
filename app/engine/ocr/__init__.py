"""OCR provider interfaces and implementations."""

from threading import Lock

from app.config import Settings, get_settings
from app.engine.ocr.base import (
    OCRInvalidImageError,
    OCRProvider,
    OCRProviderError,
    OCRResult,
    strip_image_metadata,
)
from app.engine.ocr.gcv import GoogleCloudVisionOCRProvider
from app.engine.ocr.local_stub import LocalStubOCRProvider
from app.engine.ocr.paddleocr import PaddleOCRProvider
from app.engine.ocr.rapidocr import RapidOCRProvider
from app.engine.ocr.tesseract import TesseractOCRProvider

# Providers are stateless per call but expensive to construct: PaddleOCR loads
# model weights, Cloud Vision opens a gRPC channel. Building one per check made
# every image pay that cost, so instances are cached for the process, keyed by
# the configuration that produced them.
_PROVIDERS: dict[tuple[str, str | None], OCRProvider] = {}
_PROVIDERS_LOCK = Lock()


def get_provider(settings: Settings | None = None) -> OCRProvider:
    """Return the configured OCR provider, reusing one instance per process.

    Tests inject their own provider into ``run_check`` and never reach this
    cache; call :func:`reset_provider_cache` when a test does exercise it.
    """

    resolved = settings or get_settings()
    key = (resolved.ocr_provider.strip().casefold(), resolved.google_application_credentials)
    with _PROVIDERS_LOCK:
        provider = _PROVIDERS.get(key)
        if provider is None:
            provider = _build_provider(key[0], resolved)
            _PROVIDERS[key] = provider
        return provider


def _build_provider(provider: str, settings: Settings) -> OCRProvider:
    """Construct one provider for an already-normalized provider name."""

    if provider == "rapidocr":
        return RapidOCRProvider()
    if provider == "gcv":
        return GoogleCloudVisionOCRProvider(
            credentials_path=settings.google_application_credentials
        )
    if provider == "tesseract":
        return TesseractOCRProvider()
    if provider == "paddleocr":
        return PaddleOCRProvider()
    if provider in {"local_stub", "local", "on_prem", "on-prem"}:
        return LocalStubOCRProvider()

    raise ValueError(f"Unsupported OCR_PROVIDER: {settings.ocr_provider}")


def reset_provider_cache() -> None:
    """Drop cached providers so the next call rebuilds from current settings."""

    with _PROVIDERS_LOCK:
        _PROVIDERS.clear()


async def warmup_provider(settings: Settings | None = None) -> None:
    """Build the configured provider and load whatever it needs up front.

    Providers that carry no startup cost expose no ``warmup``; for them this is
    just the construction above. Callers treat failures as non-fatal — a real
    check still reports the provider fault through the normal ``ocr_error``
    path rather than taking the process down at boot.
    """

    provider = get_provider(settings)
    warmup = getattr(provider, "warmup", None)
    if warmup is None:
        return
    await warmup()


__all__ = [
    "GoogleCloudVisionOCRProvider",
    "LocalStubOCRProvider",
    "OCRInvalidImageError",
    "OCRProvider",
    "OCRProviderError",
    "OCRResult",
    "PaddleOCRProvider",
    "RapidOCRProvider",
    "TesseractOCRProvider",
    "get_provider",
    "reset_provider_cache",
    "strip_image_metadata",
    "warmup_provider",
]
