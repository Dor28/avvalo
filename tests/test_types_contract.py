"""Engine type-contract tests (V1_TECHNICAL_PLAN §6).

§6 is the source of truth for the shapes that cross module boundaries and get
written to the (content-free) event row as ``.value`` strings. A silent rename
here would break persistence and channel parity, so the enums and model fields
are pinned to the spec.
"""

from app.engine.types import (
    CheckInput,
    CheckResult,
    CheckStatus,
    DraftOutput,
    InputType,
    Language,
    RuleHit,
    Signal,
    SituationType,
)


def test_language_enum_values() -> None:
    assert {lang.value for lang in Language} == {"uz_latn", "ru"}


def test_input_type_enum_values() -> None:
    assert {it.value for it in InputType} == {"text", "image"}


def test_check_status_enum_values() -> None:
    assert {status.value for status in CheckStatus} == {
        "ok",
        "no_signal",
        "empty_input",
        "meta",
        "off_topic",
        "low_ocr",
        "rate_limited",
        "timeout",
        "llm_error",
        "ocr_error",
        "safety_fallback",
        "unsupported_media",
    }


def test_check_input_fields_and_ephemeral_defaults() -> None:
    fields = CheckInput.model_fields
    assert {"user_key", "language", "input_type"} <= fields.keys()
    assert "face" not in fields, "the retired product-face discriminator must stay gone"
    # Ephemeral content is optional and defaults to None (§6 / §0.4).
    for ephemeral in ("raw_text", "image_bytes", "caption"):
        assert fields[ephemeral].default is None


def test_situation_type_enum_values() -> None:
    assert {kind.value for kind in SituationType} == {"checkable", "off_topic"}


def test_draft_output_contract() -> None:
    assert set(DraftOutput.model_fields) == {
        "situation_type",
        "red_flags",
        "pattern",
        "verify",
        "ask",
        "addressed_rule_ids",
    }
    empty = DraftOutput()
    assert empty.red_flags == [] and empty.verify == [] and empty.ask == []
    assert empty.pattern is None
    # Fail-safe direction: an omitted classification must run a real check
    # rather than redirect the user away from a possible situation.
    assert empty.situation_type is SituationType.checkable


def test_rule_hit_and_signal_contract() -> None:
    assert {"rule_id", "family", "message_key", "severity"} <= RuleHit.model_fields.keys()
    assert RuleHit.model_fields["severity"].default == 1
    assert set(Signal.model_fields) == {"kind", "note"}


def test_check_result_carries_metrics_and_safety_flags() -> None:
    fields = CheckResult.model_fields
    for metric in (
        "status",
        "check_id",
        "language",
        "input_type",
        "rule_ids",
        "no_signal",
        "safety_blocked",
        "latency_ms",
        "ocr_ms",
        "llm_ms",
        "ocr_confidence",
        "input_tokens",
        "output_tokens",
        "cost_usd",
        "error_class",
    ):
        assert metric in fields, f"CheckResult missing §6 field '{metric}'"
