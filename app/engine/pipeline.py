"""T4 engine pipeline skeleton.

The real rule, minimization, LLM, validation, and formatting stages land in
later tasks. This module wires their boundaries now and records only the
privacy-safe event metadata already allowed by the schema.
"""

from collections.abc import Awaitable, Callable
from time import perf_counter

from sqlalchemy.ext.asyncio import AsyncSession

from app.data import repo
from app.engine.faces import FACES
from app.engine.types import (
    CheckInput,
    CheckResult,
    CheckStatus,
    DraftOutput,
    InputType,
    RuleHit,
    Signal,
)

_Stage = Callable[[CheckInput], Awaitable[CheckResult]]


async def run_check(check_input: CheckInput, session: AsyncSession | None = None) -> CheckResult:
    """Run one check through the current skeleton stages.

    Passing ``session`` records a ``check_event`` row with IDs, status, and
    metrics only. The caller still owns the transaction.
    """

    started = perf_counter()
    result = await _run_stub_stages(check_input)
    result.latency_ms = max(0, round((perf_counter() - started) * 1000))

    if session is not None:
        await _record_event(session, check_input, result)

    return result


async def _run_stub_stages(check_input: CheckInput) -> CheckResult:
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

    signals = await _detect_signals_stub(text)
    rule_hits = await _run_rules_stub(text)
    draft = await _draft_stub(rule_hits, signals)
    no_signal = not rule_hits and not draft.red_flags
    status = CheckStatus.no_signal if no_signal else CheckStatus.ok

    return _result(
        check_input,
        status,
        text=_format_stub(draft),
        rule_ids=[hit.rule_id for hit in rule_hits],
        no_signal=no_signal,
    )


def _extract_text(check_input: CheckInput) -> str:
    return (check_input.raw_text or check_input.caption or "").strip()


async def _detect_signals_stub(_text: str) -> list[Signal]:
    return [Signal(kind="t4_pipeline_stub", note="placeholder local signal")]


async def _run_rules_stub(_text: str) -> list[RuleHit]:
    return [
        RuleHit(
            rule_id="t4.stub.pipeline",
            family="pipeline_skeleton",
            message_key="pipeline_stub",
            severity=1,
        )
    ]


async def _draft_stub(_rule_hits: list[RuleHit], _signals: list[Signal]) -> DraftOutput:
    return DraftOutput(
        red_flags=["Pipeline skeleton reached the draft stage."],
        pattern="pipeline_skeleton",
        verify=["Use official channels you find yourself before acting."],
        ask=["Would you like to check another message?"],
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
) -> CheckResult:
    return CheckResult(
        status=status,
        text=text,
        rule_ids=rule_ids or [],
        no_signal=no_signal,
        language=check_input.language,
        input_type=check_input.input_type,
        error_class=error_class,
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
