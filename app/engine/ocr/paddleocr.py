"""Local PaddleOCR provider — CPU-friendly on-prem OCR (PP-OCRv5)."""

from __future__ import annotations

import asyncio
from io import BytesIO
from typing import Any

from PIL import Image

from app.engine.ocr.base import (
    OCRInvalidImageError,
    OCRProviderError,
    OCRResult,
    strip_image_metadata,
)

# PaddleOCR groups models by script rather than combining languages in one call
# the way Tesseract's "rus+uzb+uzb_cyrl" does, so we try each configured
# language in turn and keep the best result. "uz" = Uzbek (Latin script); "ru" =
# Russian (Cyrillic script) — also the closest match for UZ-Cyrillic text, since
# PaddleOCR has no separate uz-Cyrillic model. Benchmark both against real
# screenshots before relying on this order.
_DEFAULT_LANGS: tuple[str, ...] = ("uz", "ru")
_GOOD_ENOUGH_CONFIDENCE = 0.8


class PaddleOCRProvider:
    """Run local PaddleOCR on metadata-stripped images.

    Tries each configured language and keeps the highest-confidence result,
    stopping early once one is clearly good enough. Model weights download
    from Hugging Face on first use per language (not from PaddleOCR's Chinese
    BOS mirror, which is the fallback only) — build-time warmup avoids that
    latency hitting a real user's first check.
    """

    def __init__(self, *, langs: tuple[str, ...] = _DEFAULT_LANGS) -> None:
        self.langs = langs
        self._engines: dict[str, Any] = {}

    async def extract(self, image_bytes: bytes) -> OCRResult:
        """Extract text with local PaddleOCR in a worker thread."""

        stripped = strip_image_metadata(image_bytes)
        return await asyncio.to_thread(self._extract_sync, stripped)

    def _extract_sync(self, image_bytes: bytes) -> OCRResult:
        try:
            import numpy as np

            with Image.open(BytesIO(image_bytes)) as image:
                array = np.array(image.convert("RGB"))
        except Exception as exc:
            raise OCRInvalidImageError(
                "paddleocr could not decode the image", error_code=type(exc).__name__
            ) from exc

        best: OCRResult | None = None
        for lang in self.langs:
            try:
                candidate = self._run_engine(lang, array)
            except Exception as exc:
                raise OCRProviderError(
                    "paddleocr OCR failed; ensure paddleocr and paddlepaddle are installed",
                    error_code=type(exc).__name__,
                ) from exc

            if best is None or candidate.confidence > best.confidence:
                best = candidate
            if best.text and best.confidence >= _GOOD_ENOUGH_CONFIDENCE:
                break

        assert best is not None
        return best

    def _run_engine(self, lang: str, image: Any) -> OCRResult:
        engine = self._engines.get(lang)
        if engine is None:
            from paddleocr import PaddleOCR

            engine = PaddleOCR(lang=lang, use_textline_orientation=True)
            self._engines[lang] = engine

        texts: list[str] = []
        scores: list[float] = []
        for page in engine.predict(image) or []:
            payload = getattr(page, "json", None) or {}
            payload = payload.get("res", payload)
            texts.extend(t for t in (payload.get("rec_texts") or []) if t)
            scores.extend(float(s) for s in (payload.get("rec_scores") or []))

        text = "\n".join(texts).strip()
        confidence = (sum(scores) / len(scores)) if scores else 0.0
        return OCRResult(text=text, confidence=max(0.0, min(1.0, confidence)))


__all__ = ["PaddleOCRProvider"]
