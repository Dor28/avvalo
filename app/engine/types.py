"""Pydantic contracts shared by the Avvalo engine pipeline."""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class Language(StrEnum):
    """Supported output languages/scripts."""

    uz_latn = "uz_latn"
    uz_cyrl = "uz_cyrl"
    ru = "ru"


class InputType(StrEnum):
    """Supported check input types."""

    text = "text"
    image = "image"


class CheckStatus(StrEnum):
    """Terminal statuses a check can return."""

    ok = "ok"
    no_signal = "no_signal"
    empty_input = "empty_input"
    low_ocr = "low_ocr"
    rate_limited = "rate_limited"
    timeout = "timeout"
    llm_error = "llm_error"
    safety_fallback = "safety_fallback"
    unsupported_media = "unsupported_media"


class CheckInput(BaseModel):
    """Input to one check.

    ``raw_text``, ``image_bytes``, and ``caption`` are ephemeral. They may be
    used during the request but must never be persisted.
    """

    face: str
    user_key: str
    language: Language
    input_type: InputType
    raw_text: str | None = None
    image_bytes: bytes | None = None
    caption: str | None = None


class Signal(BaseModel):
    """Structured local signal safe to pass downstream."""

    kind: str
    note: str | None = None


class RuleHit(BaseModel):
    """A deterministic rule hit."""

    rule_id: str
    family: str
    message_key: str
    severity: int = 1


class DraftOutput(BaseModel):
    """The JSON-mode draft expected from the LLM layer."""

    red_flags: list[str] = Field(default_factory=list)
    pattern: str | None = None
    verify: list[str] = Field(default_factory=list)
    ask: list[str] = Field(default_factory=list)


class CheckResult(BaseModel):
    """Final result returned to a bot or web caller."""

    status: CheckStatus
    check_id: UUID | None = None
    text: str | None = None
    rule_ids: list[str] = Field(default_factory=list)
    no_signal: bool = False
    safety_blocked: bool = False
    language: Language
    input_type: InputType
    latency_ms: int = 0
    ocr_ms: int | None = None
    llm_ms: int | None = None
    ocr_confidence: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    error_class: str | None = None
