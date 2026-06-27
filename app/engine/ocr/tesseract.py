"""Offline Tesseract OCR provider for local development."""

from __future__ import annotations

import asyncio
from io import BytesIO
from typing import Any

from PIL import Image

from app.engine.ocr.base import OCRProviderError, OCRResult, strip_image_metadata


class TesseractOCRProvider:
    """Run local Tesseract OCR on metadata-stripped images."""

    def __init__(self, *, languages: str = "rus+uzb+uzb_cyrl+eng") -> None:
        self.languages = languages

    async def extract(self, image_bytes: bytes) -> OCRResult:
        """Extract text with local Tesseract in a worker thread."""

        stripped = strip_image_metadata(image_bytes)
        return await asyncio.to_thread(self._extract_sync, stripped)

    def _extract_sync(self, image_bytes: bytes) -> OCRResult:
        try:
            import pytesseract

            with Image.open(BytesIO(image_bytes)) as image:
                text = pytesseract.image_to_string(image, lang=self.languages).strip()
                data = pytesseract.image_to_data(
                    image,
                    lang=self.languages,
                    output_type=pytesseract.Output.DICT,
                )
        except Exception as exc:
            raise OCRProviderError(
                "tesseract OCR failed; ensure the binary and language packs are installed"
            ) from exc

        return OCRResult(text=text, confidence=_confidence_from_data(data))


def _confidence_from_data(data: dict[str, Any]) -> float:
    values: list[float] = []
    for raw in data.get("conf", []):
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value >= 0:
            values.append(value / 100)

    if not values:
        return 0.0
    return max(0.0, min(1.0, sum(values) / len(values)))
