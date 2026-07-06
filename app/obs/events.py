"""Privacy-safe event logging.

This module intentionally accepts only metadata fields. Submitted content,
OCR text, model output, contact details, and identifiers that could point back
to content must be rejected before they reach logs or analytics.
"""

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Any

LOGGER = logging.getLogger(__name__)

ALLOWED_EVENT_NAMES = {
    "consent_shown",
    "consent_accepted",
    "check_started",
    "check_completed",
    "check_failed",
    "usefulness_answered",
    "decision_answered",
    "share_clicked",
    "share_tapped",
    "deletion_requested",
    "deletion_completed",
}

ALLOWED_FIELDS = {
    "cost_usd",
    "error_class",
    "face",
    "input_tokens",
    "input_type",
    "language",
    "latency",
    "latency_ms",
    "limit",
    "llm_ms",
    "next_action",
    "no_signal",
    "ocr_confidence",
    "ocr_ms",
    "output_tokens",
    "rule_ids",
    "safety_blocked",
    "status",
    "tokens",
    "usefulness",
}

CONTENT_FIELD_TOKENS = (
    "body",
    "caption",
    "card",
    "contact",
    "content",
    "email",
    "file",
    "image",
    "link",
    "message",
    "name",
    "ocr_text",
    "password",
    "phone",
    "prompt",
    "raw",
    "secret",
    "text",
    "url",
    "username",
)
CONTENT_VALUE_PATTERNS = (
    re.compile(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b"),
    re.compile(r"(?i)\b(?:https?|hxxps?)://[^\s<>()]+|\bwww\.[^\s<>()]+"),
    re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{6,}\d)(?!\d)"),
    re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"),
    re.compile(r"(?i)(?<![a-z0-9])(?:[a-z]{2}\s?\d{7})(?![a-z0-9])"),
)


def log_event(name: str, **fields: Any) -> dict[str, Any]:
    """Log one metadata-only event and return the normalized payload."""

    if name not in ALLOWED_EVENT_NAMES:
        raise ValueError(f"Unsupported event name: {name}")

    normalized: dict[str, Any] = {}
    for key, value in fields.items():
        _validate_field_name(key)
        normalized[key] = _normalize_value(value)

    payload = {"event": name, **normalized}
    LOGGER.info("event=%s fields=%s", name, normalized)
    return payload


def _validate_field_name(key: str) -> None:
    lowered = key.casefold()
    if key not in ALLOWED_FIELDS:
        raise ValueError(f"Unsupported event field: {key}")
    if any(token in lowered for token in CONTENT_FIELD_TOKENS):
        raise ValueError(f"Content-like event field is forbidden: {key}")


def _normalize_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, str):
        _validate_string_value(value)
        return value
    if isinstance(value, tuple | set):
        normalized = list(value)
        for item in normalized:
            _validate_metadata_value(item)
        return normalized
    if isinstance(value, list):
        for item in value:
            _validate_metadata_value(item)
        return value
    return value


def _validate_metadata_value(value: Any) -> None:
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, str):
        _validate_string_value(value)


def _validate_string_value(value: str) -> None:
    if any(pattern.search(value) for pattern in CONTENT_VALUE_PATTERNS):
        raise ValueError("Content-like event value is forbidden")
