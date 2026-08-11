"""Local QR-decoder contracts and content-shape helpers (technical plan §3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


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
    """Recognize a structurally valid EMVCo payload without reading its claims."""

    data = payload.encode("utf-8")
    if len(data) < 20:
        return False

    offset = 0
    first_field = True
    while offset < len(data):
        if offset + 4 > len(data):
            return False
        tag = data[offset : offset + 2]
        length_bytes = data[offset + 2 : offset + 4]
        if not tag.isdigit() or not length_bytes.isdigit():
            return False

        length = int(length_bytes)
        value_start = offset + 4
        value_end = value_start + length
        if value_end > len(data):
            return False
        value = data[value_start:value_end]

        if first_field:
            if tag != b"00" or value != b"01":
                return False
            first_field = False

        if tag == b"63":
            if length != 4 or value_end != len(data):
                return False
            if any(byte not in b"0123456789ABCDEFabcdef" for byte in value):
                return False
            try:
                supplied_crc = int(value, 16)
            except ValueError:
                return False
            return supplied_crc == _crc16_ccitt_false(data[:value_start])

        offset = value_end

    return False


def _crc16_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


__all__ = [
    "QRCodeDecoder",
    "QRDecodeResult",
    "QRDecoderError",
    "is_emvco_payment_payload",
]
