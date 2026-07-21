"""Shared engine pipeline with local rules/lookups and safe semantic analysis.

Every channel uses this orchestration. Submitted content remains ephemeral;
only allowlisted IDs, enums, component versions, and metrics are recorded.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import perf_counter
from typing import TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.data import repo
from app.engine.faces import FACES, Face
from app.engine.format import format_fallback, format_result, format_status_message
from app.engine.knowledge import (
    KnowledgeCard,
    KnowledgeRouter,
    KnowledgeStore,
    RetrievalResult,
    RouterResponse,
    retrieve_knowledge,
)
from app.engine.knowledge.router import OpenAICompatibleKnowledgeRouter
from app.engine.language import resolve_content_language
from app.engine.llm import (
    LLMProvider,
    LLMProviderError,
    LLMResponse,
    OpenAICompatibleProvider,
    build_prompt,
    draft_output_schema,
)
from app.engine.minimize import minimize
from app.engine.ocr import OCRInvalidImageError, OCRProvider, OCRProviderError
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
from app.engine.url_reputation import (
    DatabaseURLReputationStore,
    URLReputationStore,
    lookup_url_reputation,
)
from app.engine.validate import validate
from app.obs.cost import estimate_llm_cost_from_settings
from app.obs.events import log_error, log_event

_Stage = Callable[[CheckInput], Awaitable[CheckResult]]
_DEFAULT_MAX_OUTPUT_TOKENS = 600
_DEFAULT_OCR_MIN_CONFIDENCE = 0.5
_T = TypeVar("_T")


class _UnavailableKnowledgeRouter:
    """Mark an enabled-but-misconfigured router as degraded on empty recall."""

    async def route(self, **_kwargs) -> RouterResponse:
        raise RuntimeError("knowledge router unavailable")

# Outcomes that consume a daily-limit slot: a real completion (ok / no_signal)
# or a safety fallback that still ran the model. Every other status is a
# pre-analysis or system fault and is refunded so it doesn't burn the quota.
# Public because the web channel's per-IP limit applies the same refund rule.
BILLABLE_STATUSES = frozenset(
    {CheckStatus.ok, CheckStatus.no_signal, CheckStatus.safety_fallback}
)


async def run_check(
    check_input: CheckInput,
    session: AsyncSession | None = None,
    *,
    llm_provider: LLMProvider | None = None,
    fallback_llm_provider: LLMProvider | None = None,
    ocr_provider: OCRProvider | None = None,
    knowledge_store: KnowledgeStore | None = None,
    knowledge_router: KnowledgeRouter | None = None,
    url_reputation_store: URLReputationStore | None = None,
    settings: Settings | None = None,
    rate_limit_override: int | None = None,
) -> CheckResult:
    """Run one check through the current skeleton stages.

    Passing ``session`` records a ``check_event`` row with IDs, status, and
    metrics only. The caller still owns the transaction.
    """

    started = perf_counter()
    _log_check_started(check_input)

    result = (
        await _rate_limit_result(
            session, check_input, settings=settings, limit_override=rate_limit_override
        )
        if session is not None
        else None
    )
    if result is None:
        result = await _run_stages(
            check_input,
            llm_provider=llm_provider,
            fallback_llm_provider=fallback_llm_provider,
            ocr_provider=ocr_provider,
            knowledge_store=knowledge_store,
            knowledge_router=knowledge_router,
            url_reputation_store=url_reputation_store,
            session=session,
            settings=settings,
        )
    result.latency_ms = max(0, round((perf_counter() - started) * 1000))
    _log_check_finished(
        check_input, result, limit_override=rate_limit_override, settings=settings
    )

    if session is not None:
        if check_input.face in FACES and result.status not in BILLABLE_STATUSES:
            await repo.refund_usage(
                session, user_key=check_input.user_key, face=check_input.face
            )
        result.check_id = await _record_event(session, check_input, result)

    return result


async def _rate_limit_result(
    session: AsyncSession,
    check_input: CheckInput,
    *,
    settings: Settings | None = None,
    limit_override: int | None = None,
) -> CheckResult | None:
    face = FACES.get(check_input.face)
    if face is None:
        return None

    count = await repo.increment_usage(session, user_key=check_input.user_key, face=face.id)
    limit = limit_override or _daily_limit(face, settings)
    if count <= limit:
        return None

    return _result(
        check_input,
        CheckStatus.rate_limited,
        text=format_status_message(CheckStatus.rate_limited, check_input.language),
        error_class="DailyLimitExceeded",
    )


def _log_check_started(check_input: CheckInput) -> None:
    log_event(
        "check_started",
        face=check_input.face,
        input_type=check_input.input_type,
        language=check_input.language,
    )


def _daily_limit(face: Face, settings: Settings | None) -> int:
    """Resolve a face's daily limit, honoring configured overrides when present."""

    if settings is not None:
        configured = settings.daily_limit_for(face.id)
        if configured is not None:
            return configured
    return face.daily_limit


def _log_check_finished(
    check_input: CheckInput,
    result: CheckResult,
    *,
    limit_override: int | None = None,
    settings: Settings | None = None,
) -> None:
    event_name = (
        "check_completed"
        if result.status in {CheckStatus.ok, CheckStatus.no_signal}
        else "check_failed"
    )
    fields = {
        "cost_usd": result.cost_usd,
        "error_class": result.error_class,
        "face": check_input.face,
        "input_tokens": result.input_tokens,
        "input_type": result.input_type,
        "kb_version": result.kb_version,
        "knowledge_card_ids": result.knowledge_card_ids,
        "language": result.language,
        "latency_ms": result.latency_ms,
        "limit": _event_limit(check_input, limit_override, settings),
        "llm_ms": result.llm_ms,
        "no_signal": result.no_signal,
        "ocr_confidence": result.ocr_confidence,
        "ocr_ms": result.ocr_ms,
        "output_tokens": result.output_tokens,
        "rule_ids": result.rule_ids,
        "retrieval_mode": result.retrieval_mode,
        "retrieval_status": result.retrieval_status,
        "router_status": result.router_status,
        "reviewed_case_ids": result.reviewed_case_ids,
        "safety_blocked": result.safety_blocked,
        "status": result.status,
    }
    log_event(event_name, **{key: value for key, value in fields.items() if value is not None})


def _event_limit(
    check_input: CheckInput, limit_override: int | None, settings: Settings | None
) -> int | None:
    if limit_override is not None:
        return limit_override
    face = FACES.get(check_input.face)
    if face is None:
        return None
    return _daily_limit(face, settings)


async def _run_stages(
    check_input: CheckInput,
    *,
    llm_provider: LLMProvider | None,
    fallback_llm_provider: LLMProvider | None,
    ocr_provider: OCRProvider | None,
    knowledge_store: KnowledgeStore | None,
    knowledge_router: KnowledgeRouter | None,
    url_reputation_store: URLReputationStore | None,
    session: AsyncSession | None,
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
        return _result(
            check_input,
            CheckStatus.empty_input,
            text=format_status_message(CheckStatus.empty_input, check_input.language),
        )

    effective_input = check_input.model_copy(
        update={"language": resolve_content_language(text, fallback=check_input.language)}
    )
    rule_hits, signals = run_rules(text, check_input.face)
    reputation_enabled = (
        url_reputation_store is not None
        if settings is None
        else settings.url_reputation_enabled
    )
    reputation_store = url_reputation_store
    if reputation_enabled and reputation_store is None and session is not None:
        reputation_store = DatabaseURLReputationStore(session)
    if reputation_enabled and reputation_store is not None:
        try:
            reputation_hits = await lookup_url_reputation(text, store=reputation_store)
        except Exception:
            log_error(
                stage="url_reputation",
                error_type="URLReputationLookupError",
                face=check_input.face,
            )
        else:
            existing_rule_ids = {hit.rule_id for hit in rule_hits}
            rule_hits.extend(
                hit for hit in reputation_hits if hit.rule_id not in existing_rule_ids
            )
    minimized_text = minimize(text, signals)
    resolved_router = knowledge_router
    if (
        resolved_router is None
        and settings is not None
        and settings.knowledge_router_enabled
    ):
        try:
            resolved_router = OpenAICompatibleKnowledgeRouter.from_settings(settings)
        except ValueError:
            # Recall failure must never prevent the answer model from running.
            log_error(
                stage="knowledge",
                error_type="KnowledgeRouterConfigError",
                face=check_input.face,
            )
            resolved_router = _UnavailableKnowledgeRouter()
    retrieval = await retrieve_knowledge(
        face_id=check_input.face,
        minimized_text=minimized_text,
        rule_hits=rule_hits,
        signals=signals,
        store=knowledge_store,
        router=resolved_router,
    )
    llm_result = await _call_llm(
        effective_input,
        minimized_text=minimized_text,
        rule_hits=rule_hits,
        signals=signals,
        knowledge_cards=list(retrieval.cards),
        llm_provider=llm_provider,
        fallback_llm_provider=fallback_llm_provider,
        settings=settings,
        ocr_ms=content.ocr_ms,
        ocr_confidence=content.ocr_confidence,
        initial_input_tokens=retrieval.router_input_tokens,
        initial_output_tokens=retrieval.router_output_tokens,
    )
    if llm_result.status is not None:
        return _attach_retrieval(llm_result.status, retrieval)

    assert llm_result.response is not None
    draft = llm_result.response.draft
    no_signal = not rule_hits and not draft.red_flags
    status = CheckStatus.no_signal if no_signal else CheckStatus.ok

    return _result(
        effective_input,
        status,
        text=format_result(draft, effective_input.language, no_signal=no_signal),
        rule_ids=[hit.rule_id for hit in rule_hits],
        knowledge_card_ids=retrieval.knowledge_card_ids,
        reviewed_case_ids=retrieval.reviewed_case_ids,
        retrieval_mode=retrieval.mode,
        retrieval_status=retrieval.status,
        router_status=retrieval.router_status,
        kb_version=retrieval.kb_version,
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
            status=_result(
                check_input,
                CheckStatus.unsupported_media,
                text=format_status_message(CheckStatus.unsupported_media, check_input.language),
            ),
        )

    if not check_input.image_bytes:
        return _ContentStageResult(
            text=None,
            status=_result(
                check_input,
                CheckStatus.unsupported_media,
                text=format_status_message(CheckStatus.unsupported_media, check_input.language),
                error_class="missing_image_bytes",
            ),
        )

    try:
        provider = ocr_provider or get_ocr_provider(settings)
    except ValueError:
        # Misconfigured OCR_PROVIDER — an operator fault, not the user's image.
        log_error(stage="ocr", error_type="OCRConfigError", face=check_input.face)
        return _ContentStageResult(
            text=None,
            status=_result(
                check_input,
                CheckStatus.ocr_error,
                text=format_status_message(CheckStatus.ocr_error, check_input.language),
                error_class="OCRConfigError",
            ),
        )

    started = perf_counter()
    timeout_s = settings.ocr_timeout_s if settings is not None else 30.0
    try:
        ocr_result = await _with_timeout(provider.extract(check_input.image_bytes), timeout_s)
    except (TimeoutError, NotImplementedError, OCRProviderError) as exc:
        return _ocr_failure(check_input, exc, started=started, timeout_s=timeout_s)

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
                text=format_status_message(CheckStatus.low_ocr, check_input.language),
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


def _ocr_failure_status(exc: Exception) -> CheckStatus:
    """Map one OCR failure to a user-facing status: a slow provider is a
    timeout, an unreadable image or a stub provider is an input problem, and
    anything else is a provider fault the user should simply retry later."""

    if isinstance(exc, TimeoutError):
        return CheckStatus.timeout
    if isinstance(exc, OCRInvalidImageError | NotImplementedError):
        return CheckStatus.unsupported_media
    return CheckStatus.ocr_error


def _ocr_failure(
    check_input: CheckInput,
    exc: Exception,
    *,
    started: float,
    timeout_s: float,
) -> _ContentStageResult:
    ocr_ms = max(0, round((perf_counter() - started) * 1000))
    status = _ocr_failure_status(exc)
    # Only content-free metadata leaves here: the underlying exception class
    # name, never the provider's message.
    error_class = getattr(exc, "error_code", None) or type(exc).__name__
    fields: dict[str, object] = {"face": check_input.face}
    if isinstance(exc, TimeoutError):
        fields["timeout_s"] = timeout_s
    log_error(stage="ocr", error_type=error_class, **fields)
    return _ContentStageResult(
        text=None,
        ocr_ms=ocr_ms,
        status=_result(
            check_input,
            status,
            text=format_status_message(status, check_input.language),
            ocr_ms=ocr_ms,
            error_class=error_class,
        ),
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
    knowledge_cards: list[KnowledgeCard],
    llm_provider: LLMProvider | None,
    fallback_llm_provider: LLMProvider | None,
    settings: Settings | None,
    ocr_ms: int | None,
    ocr_confidence: float | None,
    initial_input_tokens: int = 0,
    initial_output_tokens: int = 0,
) -> _LLMStageResult:
    resolved_settings = settings
    provider = llm_provider
    if provider is None:
        resolved_settings = resolved_settings or get_settings()
        provider = OpenAICompatibleProvider.from_settings(resolved_settings)
    fallback_provider = fallback_llm_provider or _configured_fallback_provider(resolved_settings)

    system, user = build_prompt(
        face_id=check_input.face,
        language=check_input.language,
        minimized_text=minimized_text,
        rule_hits=rule_hits,
        signals=signals,
        knowledge_cards=knowledge_cards,
    )
    started = perf_counter()
    max_output_tokens = (
        resolved_settings.max_output_tokens
        if resolved_settings is not None
        else _DEFAULT_MAX_OUTPUT_TOKENS
    )
    total_input_tokens = initial_input_tokens
    total_output_tokens = initial_output_tokens
    validation_reason = "draft failed deterministic safety validation"

    for attempt in range(2):
        attempt_system = system if attempt == 0 else _retry_system_prompt(system, validation_reason)
        llm_timeout_s = (
            resolved_settings.llm_timeout_s if resolved_settings is not None else 30.0
        )
        try:
            response = await _with_timeout(
                provider.analyze(
                    system=attempt_system,
                    user=user,
                    schema=draft_output_schema(),
                    max_output_tokens=max_output_tokens,
                ),
                llm_timeout_s,
            )
        except (TimeoutError, LLMProviderError) as exc:
            if fallback_provider is None:
                return _llm_failure(
                    check_input,
                    exc,
                    started=started,
                    attempt=attempt,
                    timeout_s=llm_timeout_s,
                    rule_hits=rule_hits,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    settings=resolved_settings,
                    ocr_ms=ocr_ms,
                    ocr_confidence=ocr_confidence,
                )
            _log_llm_error(check_input, exc, attempt=attempt, timeout_s=llm_timeout_s)
            try:
                response = await _with_timeout(
                    fallback_provider.analyze(
                        system=attempt_system,
                        user=user,
                        schema=draft_output_schema(),
                        max_output_tokens=max_output_tokens,
                    ),
                    llm_timeout_s,
                )
            except (TimeoutError, LLMProviderError) as fallback_exc:
                return _llm_failure(
                    check_input,
                    fallback_exc,
                    started=started,
                    attempt=attempt,
                    timeout_s=llm_timeout_s,
                    rule_hits=rule_hits,
                    input_tokens=total_input_tokens,
                    output_tokens=total_output_tokens,
                    settings=resolved_settings,
                    ocr_ms=ocr_ms,
                    ocr_confidence=ocr_confidence,
                )

        total_input_tokens += response.input_tokens
        total_output_tokens += response.output_tokens
        validation = validate(
            response.draft,
            signals,
            rule_hits,
            check_input.language,
            knowledge_card_ids=[card.id for card in knowledge_cards],
        )
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
    log_error(
        stage="validate",
        error_type="SafetyValidationError",
        face=check_input.face,
        reason=validation_reason,
    )
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


def _llm_failure(
    check_input: CheckInput,
    exc: Exception,
    *,
    started: float,
    attempt: int,
    timeout_s: float,
    rule_hits: list[RuleHit],
    input_tokens: int,
    output_tokens: int,
    settings: Settings | None,
    ocr_ms: int | None,
    ocr_confidence: float | None,
) -> _LLMStageResult:
    """Map one failed provider call to its terminal stage result.

    Only content-free metadata leaves here: the underlying exception class
    name (``error_code``) and its HTTP status, never the provider's message.
    """

    llm_ms = max(0, round((perf_counter() - started) * 1000))
    cost_usd = _estimate_cost(input_tokens, output_tokens, settings)
    fields: dict[str, object] = {"face": check_input.face, "attempt": attempt}
    if isinstance(exc, TimeoutError):
        status = CheckStatus.timeout
        error_class = type(exc).__name__
        fields["timeout_s"] = timeout_s
    else:
        status = CheckStatus.llm_error
        error_class = getattr(exc, "error_code", None) or type(exc).__name__
        status_code = getattr(exc, "status_code", None)
        if status_code is not None:
            fields["status_code"] = status_code
    log_error(stage="llm", error_type=error_class, **fields)
    return _LLMStageResult(
        response=None,
        llm_ms=llm_ms,
        cost_usd=cost_usd,
        status=_result(
            check_input,
            status,
            text=format_status_message(status, check_input.language),
            rule_ids=[hit.rule_id for hit in rule_hits],
            error_class=error_class,
            ocr_ms=ocr_ms,
            ocr_confidence=ocr_confidence,
            llm_ms=llm_ms,
            input_tokens=input_tokens or None,
            output_tokens=output_tokens or None,
            cost_usd=cost_usd,
        ),
    )


def _log_llm_error(
    check_input: CheckInput,
    exc: Exception,
    *,
    attempt: int,
    timeout_s: float,
) -> None:
    fields: dict[str, object] = {"face": check_input.face, "attempt": attempt}
    error_class = getattr(exc, "error_code", None) or type(exc).__name__
    if isinstance(exc, TimeoutError):
        fields["timeout_s"] = timeout_s
    else:
        status_code = getattr(exc, "status_code", None)
        if status_code is not None:
            fields["status_code"] = status_code
    log_error(stage="llm", error_type=error_class, **fields)


def _configured_fallback_provider(settings: Settings | None) -> LLMProvider | None:
    if settings is None:
        return None
    api_key = settings.llm_fallback_api_key
    if not (
        settings.llm_fallback_base_url
        and api_key is not None
        and api_key.get_secret_value()
        and settings.llm_fallback_model
    ):
        return None
    return OpenAICompatibleProvider(
        base_url=settings.llm_fallback_base_url,
        api_key=api_key,
        model=settings.llm_fallback_model,
        timeout_s=settings.llm_timeout_s,
    )


def _retry_system_prompt(system: str, reason: str) -> str:
    return (
        f"{system}\n\n"
        "SAFETY RETRY: The previous JSON draft failed deterministic validation: "
        f"{reason}. Return corrected JSON only. Do not include banned verdict words, "
        "raw contact details, raw links, secret values, or instructions to use the "
        "suspicious contact path."
    )


async def _with_timeout(awaitable: Awaitable[_T], timeout_s: float) -> _T:
    """Run one provider call with the configured latency guard."""

    try:
        return await asyncio.wait_for(awaitable, timeout=timeout_s)
    except TimeoutError as exc:
        raise TimeoutError("provider call timed out") from exc


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
    knowledge_card_ids: list[str] | None = None,
    reviewed_case_ids: list[str] | None = None,
    retrieval_mode: str | None = None,
    retrieval_status: str | None = None,
    router_status: str | None = None,
    kb_version: str | None = None,
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
        knowledge_card_ids=knowledge_card_ids or [],
        reviewed_case_ids=reviewed_case_ids or [],
        retrieval_mode=retrieval_mode,
        retrieval_status=retrieval_status,
        router_status=router_status,
        kb_version=kb_version,
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
) -> UUID:
    return await repo.record_check_event(
        session,
        user_key=check_input.user_key,
        face=check_input.face,
        input_type=result.input_type.value,
        language=result.language.value,
        status=result.status.value,
        rule_ids=result.rule_ids,
        knowledge_card_ids=result.knowledge_card_ids,
        reviewed_case_ids=result.reviewed_case_ids,
        retrieval_mode=result.retrieval_mode,
        retrieval_status=result.retrieval_status,
        router_status=result.router_status,
        kb_version=result.kb_version,
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


def _attach_retrieval(result: CheckResult, retrieval: RetrievalResult) -> CheckResult:
    return result.model_copy(
        update={
            "knowledge_card_ids": retrieval.knowledge_card_ids,
            "reviewed_case_ids": retrieval.reviewed_case_ids,
            "retrieval_mode": retrieval.mode,
            "retrieval_status": retrieval.status,
            "router_status": retrieval.router_status,
            "kb_version": retrieval.kb_version,
        }
    )
