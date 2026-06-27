"""Privacy-safe event logging.

This module intentionally accepts only metadata fields. Submitted content,
OCR text, model output, contact details, and identifiers that could point back
to content must be rejected before they reach logs or analytics.
"""

from __future__ import annotations

import logging
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
    if isinstance(value, tuple | set):
        return list(value)
    return value
