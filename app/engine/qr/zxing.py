"""Offline in-process QR decoding through zxing-cpp (technical plan §3)."""

from __future__ import annotations

import asyncio
from io import BytesIO

import zxingcpp
from PIL import Image

from app.engine.ocr.base import OCRInvalidImageError, strip_image_metadata
from app.engine.qr.base import QRDecoderError, QRDecodeResult


class ZXingQRCodeDecoder:
    """Decode only QR symbols from sanitized image bytes, without network I/O."""

    async def decode(self, image_bytes: bytes) -> QRDecodeResult:
        """Run native decoding in a worker thread."""

        return await asyncio.to_thread(self._decode_sync, image_bytes)

    def _decode_sync(self, image_bytes: bytes) -> QRDecodeResult:
        try:
            sanitized = strip_image_metadata(image_bytes)
            with Image.open(BytesIO(sanitized)) as image:
                barcodes = zxingcpp.read_barcodes(
                    image.convert("RGB"),
                    formats=zxingcpp.BarcodeFormat.QRCode,
                )
        except OCRInvalidImageError:
            raise
        except Exception as exc:
            raise QRDecoderError(
                "local QR decoding failed",
                error_code=type(exc).__name__,
            ) from exc

        payloads = tuple(
            text
            for barcode in barcodes
            if (text := barcode.text.strip())
        )
        return QRDecodeResult(payloads=payloads)


__all__ = ["ZXingQRCodeDecoder"]
