"""Validation and normalization for founder-authored editorial cover photos."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from app.engine.ocr.base import MAX_IMAGE_DIMENSION, MAX_IMAGE_FRAMES, MAX_IMAGE_PIXELS

EDITORIAL_COVER_UPLOAD_MAX_BYTES = 10 * 1024 * 1024
EDITORIAL_COVER_STORED_MAX_BYTES = 5 * 1024 * 1024
EDITORIAL_COVER_MAX_DIMENSION = 1600
EDITORIAL_COVER_ALT_MAX_CHARS = 240
EDITORIAL_COVER_MEDIA_TYPE = "image/webp"
_ALLOWED_INPUT_FORMATS = {"JPEG", "PNG", "WEBP"}


@dataclass(frozen=True)
class PreparedEditorialCover:
    """A validated cover mutation ready to apply to an editorial post."""

    image_bytes: bytes | None
    media_type: str | None
    alt_uz_latn: str | None
    alt_ru: str | None
    clear: bool = False


def prepare_editorial_cover(
    *,
    image_bytes: bytes | None,
    alt_uz_latn: str,
    alt_ru: str,
    remove: bool,
    current_has_cover: bool,
) -> PreparedEditorialCover | None:
    """Validate one optional cover upload, stripping metadata and bounding its size."""

    normalized_alt_uz = _normalize_alt(alt_uz_latn)
    normalized_alt_ru = _normalize_alt(alt_ru)
    if remove:
        return PreparedEditorialCover(None, None, None, None, clear=True)

    if image_bytes is not None:
        if not image_bytes:
            raise ValueError("invalid_cover")
        if len(image_bytes) > EDITORIAL_COVER_UPLOAD_MAX_BYTES:
            raise ValueError("cover_too_large")
        _require_alt_text(normalized_alt_uz, normalized_alt_ru)
        normalized_image = _normalize_image(image_bytes)
        return PreparedEditorialCover(
            normalized_image,
            EDITORIAL_COVER_MEDIA_TYPE,
            normalized_alt_uz,
            normalized_alt_ru,
        )

    if current_has_cover:
        _require_alt_text(normalized_alt_uz, normalized_alt_ru)
        return PreparedEditorialCover(
            None,
            None,
            normalized_alt_uz,
            normalized_alt_ru,
        )

    if normalized_alt_uz or normalized_alt_ru:
        raise ValueError("cover_alt_without_image")
    return None


def _normalize_image(image_bytes: bytes) -> bytes:
    try:
        with Image.open(BytesIO(image_bytes)) as source:
            if source.format not in _ALLOWED_INPUT_FORMATS:
                raise ValueError("invalid_cover")
            width, height = source.size
            if (
                width <= 0
                or height <= 0
                or max(width, height) > MAX_IMAGE_DIMENSION
                or width * height > MAX_IMAGE_PIXELS
                or getattr(source, "n_frames", 1) > MAX_IMAGE_FRAMES
            ):
                raise ValueError("invalid_cover")

            normalized = ImageOps.exif_transpose(source)
            normalized.load()
            normalized.thumbnail(
                (EDITORIAL_COVER_MAX_DIMENSION, EDITORIAL_COVER_MAX_DIMENSION),
                Image.Resampling.LANCZOS,
            )
            if normalized.mode not in {"RGB", "RGBA"}:
                output_mode = "RGBA" if "transparency" in normalized.info else "RGB"
                normalized = normalized.convert(output_mode)

            output = BytesIO()
            normalized.save(output, format="WEBP", quality=85, method=6)
            prepared = output.getvalue()
    except (Image.DecompressionBombError, OSError, UnidentifiedImageError) as exc:
        raise ValueError("invalid_cover") from exc

    if not prepared or len(prepared) > EDITORIAL_COVER_STORED_MAX_BYTES:
        raise ValueError("cover_too_large")
    return prepared


def _normalize_alt(value: str) -> str:
    normalized = str(value).strip()
    if len(normalized) > EDITORIAL_COVER_ALT_MAX_CHARS:
        raise ValueError("cover_alt_too_long")
    return normalized


def _require_alt_text(alt_uz_latn: str, alt_ru: str) -> None:
    if not alt_uz_latn or not alt_ru:
        raise ValueError("cover_alt_required")
