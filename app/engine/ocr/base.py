"""OCR provider contracts and shared image helpers."""

from __future__ import annotations

from io import BytesIO
from typing import Protocol

from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field

MAX_IMAGE_PIXELS = 16_000_000
MAX_IMAGE_DIMENSION = 8192
MAX_IMAGE_FRAMES = 1


class OCRResult(BaseModel):
    """Extracted text and provider confidence for one image."""

    text: str
    confidence: float = Field(ge=0, le=1)


class OCRProvider(Protocol):
    """Async OCR provider interface used by the engine pipeline."""

    async def extract(self, image_bytes: bytes) -> OCRResult:
        """Return OCR text for image bytes after provider-specific processing."""


class OCRProviderError(RuntimeError):
    """Raised when OCR cannot produce a usable provider response.

    ``args[0]`` may carry provider response text and must never reach logs,
    events, or alerts. ``error_code`` (the underlying exception class name)
    is the only loggable field.
    """

    def __init__(self, message: str, *, error_code: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code


class OCRInvalidImageError(OCRProviderError):
    """The submitted bytes are not a decodable image — an input fault, not an outage."""


def strip_image_metadata(image_bytes: bytes) -> bytes:
    """Return PNG bytes with EXIF/GPS and other metadata removed."""

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            _validate_image_geometry(image)
            image = ImageOps.exif_transpose(image)
            image.load()
            if image.mode not in {"1", "L", "P", "RGB", "RGBA"}:
                image = image.convert("RGB")

            output = BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()
    except Image.DecompressionBombError as exc:
        raise OCRInvalidImageError(
            "image exceeds the safe pixel limit", error_code="ImagePixelLimitExceeded"
        ) from exc
    except (OSError, UnidentifiedImageError) as exc:
        raise OCRInvalidImageError(
            "image bytes are not a readable image", error_code=type(exc).__name__
        ) from exc


def _validate_image_geometry(image: Image.Image) -> None:
    width, height = image.size
    if width <= 0 or height <= 0:
        raise OCRInvalidImageError(
            "image dimensions are invalid", error_code="ImageDimensionInvalid"
        )
    if max(width, height) > MAX_IMAGE_DIMENSION:
        raise OCRInvalidImageError(
            "image dimension exceeds the safe limit",
            error_code="ImageDimensionLimitExceeded",
        )
    if width * height > MAX_IMAGE_PIXELS:
        raise OCRInvalidImageError(
            "image exceeds the safe pixel limit", error_code="ImagePixelLimitExceeded"
        )
    if getattr(image, "n_frames", 1) > MAX_IMAGE_FRAMES:
        raise OCRInvalidImageError(
            "animated images are not supported", error_code="ImageFrameLimitExceeded"
        )
