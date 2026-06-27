"""Placeholder for future on-prem OCR."""

from app.engine.ocr.base import OCRProviderError, OCRResult


class LocalStubOCRProvider:
    """Intentional stub so the on-prem swap point is explicit."""

    async def extract(self, image_bytes: bytes) -> OCRResult:
        """Raise until the post-grant on-prem OCR implementation lands."""

        _ = image_bytes
        raise NotImplementedError("on-prem OCR is post-grant roadmap")


class OnPremOCRProvider(LocalStubOCRProvider):
    """Compatibility alias for callers looking for the on-prem provider."""


__all__ = ["LocalStubOCRProvider", "OCRProviderError", "OnPremOCRProvider"]
