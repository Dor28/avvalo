"""OCR provider interfaces and implementations."""

from app.config import Settings, get_settings
from app.engine.ocr.base import (
    OCRInvalidImageError,
    OCRProvider,
    OCRProviderError,
    OCRResult,
    strip_image_metadata,
)
from app.engine.ocr.gcv import GoogleCloudVisionOCRProvider
from app.engine.ocr.local_stub import LocalStubOCRProvider, OnPremOCRProvider
from app.engine.ocr.paddleocr import PaddleOCRProvider
from app.engine.ocr.tesseract import TesseractOCRProvider


def get_provider(settings: Settings | None = None) -> OCRProvider:
    """Build the configured OCR provider."""

    resolved = settings or get_settings()
    provider = resolved.ocr_provider.strip().casefold()

    if provider == "gcv":
        return GoogleCloudVisionOCRProvider(
            credentials_path=resolved.google_application_credentials
        )
    if provider == "tesseract":
        return TesseractOCRProvider()
    if provider == "paddleocr":
        return PaddleOCRProvider()
    if provider in {"local_stub", "local", "on_prem", "on-prem"}:
        return LocalStubOCRProvider()

    raise ValueError(f"Unsupported OCR_PROVIDER: {resolved.ocr_provider}")


get_ocr_provider = get_provider
build_provider = get_provider

__all__ = [
    "GoogleCloudVisionOCRProvider",
    "LocalStubOCRProvider",
    "OCRInvalidImageError",
    "OCRProvider",
    "OCRProviderError",
    "OCRResult",
    "OnPremOCRProvider",
    "PaddleOCRProvider",
    "TesseractOCRProvider",
    "build_provider",
    "get_ocr_provider",
    "get_provider",
    "strip_image_metadata",
]
