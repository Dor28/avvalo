"""Engine pipeline skeleton with deterministic local stages.

Validation and final formatting stages land in later tasks. This module wires
the real local rule/minimization/LLM boundary and records only the privacy-safe
event metadata already allowed by the schema.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import perf_counter

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.data import repo
from app.engine.faces import FACES
from app.engine.llm import (
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    OpenAICompatibleProvider,
    build_prompt,
    draft_output_schema,
)
from app.engine.minimize import minimize
from app.engine.rules import run_rules
from app.engine.types import (
    CheckInput,
    CheckResult,
    CheckStatus,
    DraftOutput,
    InputType,
    RuleHit,
    Signal,
)
from app.obs.cost import estimate_llm_cost_from_settings

_Stage = Callable[[CheckInput], Awaitable[CheckResult]]
_DEFAULT_MAX_OUTPUT_TOKENS = 600


async def run_check(
    check_input: CheckInput,
    session: AsyncSession | None = None,
    *,
    llm_provider: LLMProvider | None = None,
    settings: Settings | None = None,
) -> CheckResult:
    """Run one check through the current skeleton stages.

    Passing ``session`` records a ``check_event`` row with IDs, status, and
    metrics only. The caller still owns the transaction.
    """

    started = perf_counter()
    result = await _run_stages(check_input, llm_provider=llm_provider, settings=settings)
    result.latency_ms = max(0, round((perf_counter() - started) * 1000))

    if session is not None:
        await _record_event(session, check_input, result)

    return result


async def _run_stages(
    check_input: CheckInput,
    *,
    llm_provider: LLMProvider | None,
    settings: Settings | None,
) -> CheckResult:
    if check_input.face not in FACES:
        return _result(check_input, CheckStatus.unsupported_media, error_class="unknown_face")

    if check_input.input_type is InputType.image:
        return _result(
            check_input,
            CheckStatus.unsupported_media,
            text="Image checks are not wired yet. Please paste the text for now.",
        )

    text = _extract_text(check_input)
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
        text=_format_stub(draft),
        rule_ids=[hit.rule_id for hit in rule_hits],
        no_signal=no_signal,
        llm_ms=llm_result.llm_ms,
        input_tokens=llm_result.response.input_tokens,
        output_tokens=llm_result.response.output_tokens,
        cost_usd=llm_result.cost_usd,
    )


def _extract_text(check_input: CheckInput) -> str:
    parts = [part.strip() for part in (check_input.caption, check_input.raw_text) if part]
    return "\n".join(part for part in parts if part).strip()


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
    try:
        response = await provider.analyze(
            system=system,
            user=user,
            schema=draft_output_schema(),
            max_output_tokens=(
                resolved_settings.max_output_tokens
                if resolved_settings is not None
                else _DEFAULT_MAX_OUTPUT_TOKENS
            ),
        )
    except LLMProviderError as exc:
        llm_ms = max(0, round((perf_counter() - started) * 1000))
        return _LLMStageResult(
            response=None,
            llm_ms=llm_ms,
            cost_usd=None,
            status=_result(
                check_input,
                CheckStatus.llm_error,
                text="We could not analyze this message right now. Please try again.",
                rule_ids=[hit.rule_id for hit in rule_hits],
                error_class=exc.__class__.__name__,
                llm_ms=llm_ms,
            ),
        )

    cost_usd = None
    if resolved_settings is not None:
        cost_usd = estimate_llm_cost_from_settings(
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            settings=resolved_settings,
        )

    return _LLMStageResult(
        response=response,
        llm_ms=max(0, round((perf_counter() - started) * 1000)),
        cost_usd=cost_usd,
    )


def _format_stub(draft: DraftOutput) -> str:
    blocks = [*draft.red_flags, *draft.verify, *draft.ask]
    return "\n".join(blocks)


def _result(
    check_input: CheckInput,
    status: CheckStatus,
    *,
    text: str | None = None,
    rule_ids: list[str] | None = None,
    no_signal: bool = False,
    error_class: str | None = None,
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
        language=check_input.language,
        input_type=check_input.input_type,
        error_class=error_class,
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
