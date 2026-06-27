"""Engine pipeline with deterministic local stages.

Final OCR and hardening stages land in later tasks. This module wires the real
local rule/minimization/LLM/validation boundary and records only privacy-safe
event metadata already allowed by the schema.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import perf_counter

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.data import repo
from app.engine.faces import FACES
from app.engine.format import format_fallback, format_result
from app.engine.llm import (
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    OpenAICompatibleProvider,
    build_prompt,
    draft_output_schema,
)
from app.engine.minimize import minimize
from app.engine.ocr import OCRProvider, OCRProviderError
from app.engine.ocr import get_provider as get_ocr_provider
from app.engine.rules import run_rules
from app.engine.types import (
    CheckInput,
    CheckResult,
    CheckStatus,
    InputType,
    RuleHit,
    Signal,
)
from app.engine.validate import validate
from app.obs.cost import estimate_llm_cost_from_settings

_Stage = Callable[[CheckInput], Awaitable[CheckResult]]
_DEFAULT_MAX_OUTPUT_TOKENS = 600
_DEFAULT_OCR_MIN_CONFIDENCE = 0.5


async def run_check(
    check_input: CheckInput,
    session: AsyncSession | None = None,
    *,
    llm_provider: LLMProvider | None = None,
    ocr_provider: OCRProvider | None = None,
    settings: Settings | None = None,
) -> CheckResult:
    """Run one check through the current skeleton stages.

    Passing ``session`` records a ``check_event`` row with IDs, status, and
    metrics only. The caller still owns the transaction.
    """

    started = perf_counter()
    result = await _run_stages(
        check_input,
        llm_provider=llm_provider,
        ocr_provider=ocr_provider,
        settings=settings,
    )
    result.latency_ms = max(0, round((perf_counter() - started) * 1000))

    if session is not None:
        await _record_event(session, check_input, result)

    return result


async def _run_stages(
    check_input: CheckInput,
    *,
    llm_provider: LLMProvider | None,
    ocr_provider: OCRProvider | None,
    settings: Settings | None,
) -> CheckResult:
    if check_input.face not in FACES:
        return _result(check_input, CheckStatus.unsupported_media, error_class="unknown_face")

    content = await _content_from_input(
        check_input,
        ocr_provider=ocr_provider,
        settings=settings,
    )
    if content.status is not None:
        return content.status

    text = content.text or ""
    if not text:
        return _result(check_input, CheckStatus.empty_input, text="Please send some text to check.")

    rule_hits, signals = run_rules(text, check_input.face)
    minimized_text = minimize(text, signals)
    llm_result = await _call_llm(
        check_input,
        minimized_text=minimized_text,
        rule_hits=rule_hits,
        signals=signals,
        llm_provider=llm_provider,
        settings=settings,
        ocr_ms=content.ocr_ms,
        ocr_confidence=content.ocr_confidence,
    )
    if llm_result.status is not None:
        return llm_result.status

    assert llm_result.response is not None
    draft = llm_result.response.draft
    no_signal = not rule_hits and not draft.red_flags
    status = CheckStatus.no_signal if no_signal else CheckStatus.ok

    return _result(
        check_input,
        status,
        text=format_result(draft, check_input.language, no_signal=no_signal),
        rule_ids=[hit.rule_id for hit in rule_hits],
        no_signal=no_signal,
        ocr_ms=content.ocr_ms,
        ocr_confidence=content.ocr_confidence,
        llm_ms=llm_result.llm_ms,
        input_tokens=llm_result.response.input_tokens,
        output_tokens=llm_result.response.output_tokens,
        cost_usd=llm_result.cost_usd,
    )


def _extract_text(check_input: CheckInput) -> str:
    parts = [part.strip() for part in (check_input.caption, check_input.raw_text) if part]
    return "\n".join(part for part in parts if part).strip()


@dataclass(frozen=True)
class _ContentStageResult:
    text: str | None
    status: CheckResult | None = None
    ocr_ms: int | None = None
    ocr_confidence: float | None = None


async def _content_from_input(
    check_input: CheckInput,
    *,
    ocr_provider: OCRProvider | None,
    settings: Settings | None,
) -> _ContentStageResult:
    if check_input.input_type is InputType.text:
        return _ContentStageResult(text=_extract_text(check_input))

    if check_input.input_type is not InputType.image:
        return _ContentStageResult(
            text=None,
            status=_result(check_input, CheckStatus.unsupported_media),
        )

    if not check_input.image_bytes:
        return _ContentStageResult(
            text=None,
            status=_result(
                check_input,
                CheckStatus.unsupported_media,
                text="Please send a readable image or paste the text.",
                error_class="missing_image_bytes",
            ),
        )

    started = perf_counter()
    try:
        provider = ocr_provider or get_ocr_provider(settings)
        ocr_result = await provider.extract(check_input.image_bytes)
    except NotImplementedError as exc:
        ocr_ms = max(0, round((perf_counter() - started) * 1000))
        return _ContentStageResult(
            text=None,
            ocr_ms=ocr_ms,
            status=_result(
                check_input,
                CheckStatus.unsupported_media,
                text="Image checks are not available yet. Please paste the text.",
                ocr_ms=ocr_ms,
                error_class=exc.__class__.__name__,
            ),
        )
    except OCRProviderError as exc:
        ocr_ms = max(0, round((perf_counter() - started) * 1000))
        return _ContentStageResult(
            text=None,
            ocr_ms=ocr_ms,
            status=_result(
                check_input,
                CheckStatus.unsupported_media,
                text="We could not read this image. Please paste the important text.",
                ocr_ms=ocr_ms,
                error_class=exc.__class__.__name__,
            ),
        )

    ocr_ms = max(0, round((perf_counter() - started) * 1000))
    min_confidence = (
        settings.ocr_min_confidence if settings is not None else _DEFAULT_OCR_MIN_CONFIDENCE
    )
    ocr_text = ocr_result.text.strip()
    if not ocr_text or ocr_result.confidence < min_confidence:
        return _ContentStageResult(
            text=None,
            ocr_ms=ocr_ms,
            ocr_confidence=ocr_result.confidence,
            status=_result(
                check_input,
                CheckStatus.low_ocr,
                text="We could not read the image clearly. Please paste the important text.",
                ocr_ms=ocr_ms,
                ocr_confidence=ocr_result.confidence,
            ),
        )

    parts = [part.strip() for part in (check_input.caption, ocr_text) if part and part.strip()]
    return _ContentStageResult(
        text="\n".join(parts),
        ocr_ms=ocr_ms,
        ocr_confidence=ocr_result.confidence,
    )


@dataclass(frozen=True)
class _LLMStageResult:
    response: LLMResponse | None
    llm_ms: int
    cost_usd: float | None
    status: CheckResult | None = None


async def _call_llm(
    check_input: CheckInput,
    *,
    minimized_text: str,
    rule_hits: list[RuleHit],
    signals: list[Signal],
    llm_provider: LLMProvider | None,
    settings: Settings | None,
    ocr_ms: int | None,
    ocr_confidence: float | None,
) -> _LLMStageResult:
    resolved_settings = settings
    provider = llm_provider
    if provider is None:
        resolved_settings = resolved_settings or get_settings()
        provider = OpenAICompatibleProvider.from_settings(resolved_settings)

    system, user = build_prompt(
        face_id=check_input.face,
        language=check_input.language,
        minimized_text=minimized_text,
        rule_hits=rule_hits,
        signals=signals,
    )
    started = perf_counter()
    max_output_tokens = (
        resolved_settings.max_output_tokens
        if resolved_settings is not None
        else _DEFAULT_MAX_OUTPUT_TOKENS
    )
    total_input_tokens = 0
    total_output_tokens = 0
    validation_reason = "draft failed deterministic safety validation"

    for attempt in range(2):
        attempt_system = system if attempt == 0 else _retry_system_prompt(system, validation_reason)
        try:
            response = await provider.analyze(
                system=attempt_system,
                user=user,
                schema=draft_output_schema(),
                max_output_tokens=max_output_tokens,
            )
        except LLMProviderError as exc:
            llm_ms = max(0, round((perf_counter() - started) * 1000))
            cost_usd = _estimate_cost(total_input_tokens, total_output_tokens, resolved_settings)
            return _LLMStageResult(
                response=None,
                llm_ms=llm_ms,
                cost_usd=cost_usd,
                status=_result(
                    check_input,
                    CheckStatus.llm_error,
                    text="We could not analyze this message right now. Please try again.",
                    rule_ids=[hit.rule_id for hit in rule_hits],
                    error_class=exc.__class__.__name__,
                    ocr_ms=ocr_ms,
                    ocr_confidence=ocr_confidence,
                    llm_ms=llm_ms,
                    input_tokens=total_input_tokens or None,
                    output_tokens=total_output_tokens or None,
                    cost_usd=cost_usd,
                ),
            )

        total_input_tokens += response.input_tokens
        total_output_tokens += response.output_tokens
        validation = validate(response.draft, signals, rule_hits, check_input.language)
        if validation.ok:
            safe_response = LLMResponse(
                draft=validation.draft,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
            )
            return _LLMStageResult(
                response=safe_response,
                llm_ms=max(0, round((perf_counter() - started) * 1000)),
                cost_usd=_estimate_cost(
                    total_input_tokens, total_output_tokens, resolved_settings
                ),
            )
        validation_reason = validation.reason or validation_reason

    llm_ms = max(0, round((perf_counter() - started) * 1000))
    cost_usd = _estimate_cost(total_input_tokens, total_output_tokens, resolved_settings)
    return _LLMStageResult(
        response=None,
        llm_ms=llm_ms,
        cost_usd=cost_usd,
        status=_result(
            check_input,
            CheckStatus.safety_fallback,
            text=format_fallback(check_input.language),
            rule_ids=[hit.rule_id for hit in rule_hits],
            error_class="SafetyValidationError",
            safety_blocked=True,
            ocr_ms=ocr_ms,
            ocr_confidence=ocr_confidence,
            llm_ms=llm_ms,
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
            cost_usd=cost_usd,
        ),
    )


def _retry_system_prompt(system: str, reason: str) -> str:
    return (
        f"{system}\n\n"
        "SAFETY RETRY: The previous JSON draft failed deterministic validation: "
        f"{reason}. Return corrected JSON only. Do not include banned verdict words, "
        "raw contact details, raw links, secret values, or instructions to use the "
        "suspicious contact path."
    )


def _estimate_cost(
    input_tokens: int, output_tokens: int, settings: Settings | None
) -> float | None:
    if settings is None or (input_tokens == 0 and output_tokens == 0):
        return None
    return estimate_llm_cost_from_settings(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        settings=settings,
    )


def _result(
    check_input: CheckInput,
    status: CheckStatus,
    *,
    text: str | None = None,
    rule_ids: list[str] | None = None,
    no_signal: bool = False,
    safety_blocked: bool = False,
    error_class: str | None = None,
    ocr_ms: int | None = None,
    ocr_confidence: float | None = None,
    llm_ms: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd: float | None = None,
) -> CheckResult:
    return CheckResult(
        status=status,
        text=text,
        rule_ids=rule_ids or [],
        no_signal=no_signal,
        safety_blocked=safety_blocked,
        language=check_input.language,
        input_type=check_input.input_type,
        error_class=error_class,
        ocr_ms=ocr_ms,
        ocr_confidence=ocr_confidence,
        llm_ms=llm_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
    )


async def _record_event(
    session: AsyncSession, check_input: CheckInput, result: CheckResult
) -> None:
    await repo.record_check_event(
        session,
        user_key=check_input.user_key,
        face=check_input.face,
        input_type=result.input_type.value,
        language=result.language.value,
        status=result.status.value,
        rule_ids=result.rule_ids,
        no_signal=result.no_signal,
        error_class=result.error_class,
        ocr_confidence=result.ocr_confidence,
        latency_ms=result.latency_ms,
        ocr_ms=result.ocr_ms,
        llm_ms=result.llm_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_usd=result.cost_usd,
        safety_blocked=result.safety_blocked,
    )
