"""Google Cloud Vision OCR provider."""

from __future__ import annotations

import asyncio
from typing import Any

from app.engine.ocr.base import OCRProviderError, OCRResult, strip_image_metadata


class GoogleCloudVisionOCRProvider:
    """Run Cloud Vision DOCUMENT_TEXT_DETECTION on metadata-stripped images."""

    def __init__(self, *, credentials_path: str | None = None, client: Any | None = None) -> None:
        self._credentials_path = credentials_path
        self._client = client

    async def extract(self, image_bytes: bytes) -> OCRResult:
        """Extract text with Cloud Vision without sending image metadata."""

        stripped = strip_image_metadata(image_bytes)
        try:
            vision = _vision_module()
            image = vision.Image(content=stripped)
            client = self._client or self._build_client()
            response = await asyncio.to_thread(client.document_text_detection, image=image)
        except Exception as exc:
            raise OCRProviderError("google cloud vision OCR failed") from exc

        error = getattr(response, "error", None)
        error_message = getattr(error, "message", None)
        if error_message:
            raise OCRProviderError(error_message)

        annotation = getattr(response, "full_text_annotation", None)
        text = (getattr(annotation, "text", "") or "").strip()
        return OCRResult(text=text, confidence=_average_word_confidence(annotation))

    def _build_client(self) -> Any:
        vision = _vision_module()
        if not self._credentials_path:
            return vision.ImageAnnotatorClient()

        from google.oauth2 import service_account

        credentials = service_account.Credentials.from_service_account_file(
            self._credentials_path
        )
        return vision.ImageAnnotatorClient(credentials=credentials)


def _vision_module() -> Any:
    from google.cloud import vision

    return vision


def _average_word_confidence(annotation: Any) -> float:
    if annotation is None:
        return 0.0

    confidences: list[float] = []
    for page in getattr(annotation, "pages", []) or []:
        for block in getattr(page, "blocks", []) or []:
            for paragraph in getattr(block, "paragraphs", []) or []:
                for word in getattr(paragraph, "words", []) or []:
                    confidence = getattr(word, "confidence", None)
                    if confidence is not None:
                        confidences.append(float(confidence))

    if not confidences:
        return 1.0 if (getattr(annotation, "text", "") or "").strip() else 0.0
    return max(0.0, min(1.0, sum(confidences) / len(confidences)))
