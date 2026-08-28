"""Pydantic contracts shared by the Avvalo engine pipeline."""

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

MAX_SUBMITTED_TEXT_CHARS = 6_000
MAX_IMAGE_BYTES = 10 * 1024 * 1024


class Language(StrEnum):
    """Supported reply languages.

    Uzbek is answered in Latin script only. Cyrillic-Uzbek input is still read
    and matched (see ``app.engine.language`` and the ``uz_cyrl`` keyword groups
    in the rule packs), but it resolves to :attr:`uz_latn` for the reply.
    """

    uz_latn = "uz_latn"
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
    meta = "meta"
    off_topic = "off_topic"
    low_ocr = "low_ocr"
    rate_limited = "rate_limited"
    timeout = "timeout"
    llm_error = "llm_error"
    ocr_error = "ocr_error"
    safety_fallback = "safety_fallback"
    unsupported_media = "unsupported_media"


class SituationType(StrEnum):
    """Whether the submitted content is a situation to check at all.

    ``app.engine.meta`` catches fixed chatter phrases deterministically; this is
    the model's judgement for open-ended non-situations ("what day is it") that
    no phrase list can enumerate. :attr:`checkable` is the fail-safe default: a
    model that omits or garbles the field yields a real check, never a refusal.
    """

    checkable = "checkable"
    off_topic = "off_topic"


class CheckInput(BaseModel):
    """Input to one check.

    ``raw_text``, ``image_bytes``, and ``caption`` are ephemeral. They may be
    used during the request but must never be persisted.
    """

    user_key: str
    language: Language
    input_type: InputType
    raw_text: str | None = Field(default=None, max_length=MAX_SUBMITTED_TEXT_CHARS)
    image_bytes: bytes | None = Field(default=None, max_length=MAX_IMAGE_BYTES)
    caption: str | None = Field(default=None, max_length=MAX_SUBMITTED_TEXT_CHARS)


class Signal(BaseModel):
    """Structured local signal safe to pass downstream."""

    kind: str
    note: str | None = None


class RuleHit(BaseModel):
    """A deterministic rule hit.

    ``family`` names the scam-family taxonomy bucket (credential_theft,
    urgency_secrecy, …), not any product identifier.
    """

    rule_id: str
    family: str
    message_key: str
    severity: int = 1


class Evidence(BaseModel):
    """One red-flag bullet together with the detected fact it rests on.

    ``source_id`` names a detected ``RuleHit.rule_id``, a ``Signal.kind``, or a
    selected knowledge-card id. ``app.engine.validate`` checks membership in the
    evidence set for the check, so a claim about the user's situation can only
    reach them when it can name what it rests on (PIPELINE_V2 §3).

    An empty ``source_id`` means the model did not use the field at all. That is
    a distinct case from citing an unknown id, and the validator treats the two
    differently — see ``_partition_red_flags``.
    """

    text: str
    source_id: str = ""


class DraftOutput(BaseModel):
    """The JSON-mode draft expected from the LLM layer."""

    situation_type: SituationType = SituationType.checkable
    red_flags: list[Evidence] = Field(default_factory=list)
    pattern: str | None = None
    verify: list[str] = Field(default_factory=list)
    ask: list[str] = Field(default_factory=list)
    addressed_rule_ids: list[str] = Field(default_factory=list)

    @field_validator("red_flags", mode="before")
    @classmethod
    def _coerce_red_flags(cls, value: Any) -> Any:
        """Accept bare strings so a host that ignores the nested schema still parses.

        Such a bullet carries no ``source_id`` and is handled by the validator's
        compatibility floor rather than being silently trusted.
        """

        if not isinstance(value, list):
            return value
        return [{"text": item} if isinstance(item, str) else item for item in value]


class CheckResult(BaseModel):
    """Final result returned to a bot or web caller."""

    status: CheckStatus
    check_id: UUID | None = None
    text: str | None = None
    rule_ids: list[str] = Field(default_factory=list)
    knowledge_card_ids: list[str] = Field(default_factory=list)
    reviewed_case_ids: list[str] = Field(default_factory=list)
    retrieval_mode: str | None = None
    retrieval_status: str | None = None
    router_status: str | None = None
    kb_version: str | None = None
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
