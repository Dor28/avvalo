"""Local QR-decoder contracts and content-shape helpers (technical plan §3)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

_EMVCO_CRC_RE = re.compile(r"6304[0-9A-F]{4}$", re.IGNORECASE)


@dataclass(frozen=True)
class QRDecodeResult:
    """Decoded QR payloads from one submitted image.

    Payloads are ephemeral submitted content. They must never be logged or
    persisted and may leave the content stage only through minimization.
    """

    payloads: tuple[str, ...] = ()


class QRCodeDecoder(Protocol):
    """Async local QR decoder used beside OCR in the content stage."""

    async def decode(self, image_bytes: bytes) -> QRDecodeResult:
        """Return every readable QR payload without opening any destination."""


class QRDecoderError(RuntimeError):
    """Content-safe wrapper for local decoder failures."""

    def __init__(self, message: str, *, error_code: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code


def is_emvco_payment_payload(payload: str) -> bool:
    """Recognize an EMVCo payment-QR shape without parsing its claims."""

    compact = "".join(payload.split())
    return len(compact) >= 20 and compact.startswith("000201") and bool(
        _EMVCO_CRC_RE.search(compact)
    )


__all__ = [
    "QRCodeDecoder",
    "QRDecodeResult",
    "QRDecoderError",
    "is_emvco_payment_payload",
]
