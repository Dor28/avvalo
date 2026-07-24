"""Privacy-safe CRUD over the §5.2 schema.

Every function operates on a caller-provided :class:`AsyncSession` and flushes;
the caller owns the transaction (commit/rollback). No function accepts or returns
submitted content — only pseudonymous keys, categorical fields, IDs, and metrics.
"""

import hashlib
import re
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.models import (
    CheckEvent,
    Consent,
    DeletionLog,
    Feedback,
    RateLimit,
    StorySubmission,
)

USEFULNESS_VALUES = {"yes", "partly", "no"}
NEXT_ACTION_VALUES = {"verify", "delay_stop", "continue", "not_sure"}
# The two independent daily counters sharing ``rate_limit``: the per-user limit
# and the web channel's per-IP guard, whose user_key is an IP hash.
RATE_LIMIT_SCOPES = {"user", "web_ip"}
CHECK_EVENT_INPUT_TYPES = {"text", "image"}
CHECK_EVENT_LANGUAGES = {"uz_latn", "ru"}
CHECK_EVENT_STATUSES = {
    "ok",
    "no_signal",
    "empty_input",
    "meta",
    "low_ocr",
    "rate_limited",
    "timeout",
    "llm_error",
    "ocr_error",
    "safety_fallback",
    "unsupported_media",
}
RULE_ID_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,79}$")
ERROR_CLASS_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,79}$")
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
RETRIEVAL_MODES = {"rule", "signal", "cue", "router", "none"}
RETRIEVAL_STATUSES = {
    "ok",
    "empty",
    "unavailable",
}
ROUTER_STATUSES = {"not_used", "ok", "unavailable", "invalid_ids"}


def _utcnow() -> datetime:
    return datetime.now(UTC)


async def upsert_consent(
    session: AsyncSession,
    *,
    user_key: str,
    notice_version: str,
    language: str,
) -> Consent:
    """Insert or refresh the consent row for ``user_key``."""

    row = await session.get(Consent, user_key)
    if row is None:
        row = Consent(
            user_key=user_key,
            notice_version=notice_version,
            language=language,
            ts=_utcnow(),
        )
        session.add(row)
    else:
        row.notice_version = notice_version
        row.language = language
        row.ts = _utcnow()
    await session.flush()
    return row


async def get_consent(session: AsyncSession, *, user_key: str) -> Consent | None:
    """Return the consent row for ``user_key`` or ``None``."""

    return await session.get(Consent, user_key)


async def record_check_event(
    session: AsyncSession,
    *,
    user_key: str,
    input_type: str,
    language: str,
    status: str,
    rule_ids: list[str] | None = None,
    knowledge_card_ids: list[str] | None = None,
    reviewed_case_ids: list[str] | None = None,
    retrieval_mode: str | None = None,
    retrieval_status: str | None = None,
    router_status: str | None = None,
    kb_version: str | None = None,
    no_signal: bool = False,
    error_class: str | None = None,
    ocr_confidence: float | None = None,
    latency_ms: int = 0,
    ocr_ms: int | None = None,
    llm_ms: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd: float | None = None,
    safety_blocked: bool = False,
) -> uuid.UUID:
    """Persist one privacy-safe check event and return its generated id."""

    _validate_check_event_metadata(
        input_type=input_type,
        language=language,
        status=status,
        rule_ids=rule_ids or [],
        knowledge_card_ids=knowledge_card_ids or [],
        reviewed_case_ids=reviewed_case_ids or [],
        retrieval_mode=retrieval_mode,
        retrieval_status=retrieval_status,
        router_status=router_status,
        kb_version=kb_version,
        error_class=error_class,
    )
    event = CheckEvent(
        id=uuid.uuid4(),
        user_key=user_key,
        ts=_utcnow(),
        input_type=input_type,
        language=language,
        rule_ids=list(rule_ids or []),
        knowledge_card_ids=list(knowledge_card_ids or []),
        reviewed_case_ids=list(reviewed_case_ids or []),
        retrieval_mode=retrieval_mode,
        retrieval_status=retrieval_status,
        router_status=router_status,
        kb_version=kb_version,
        no_signal=no_signal,
        status=status,
        error_class=error_class,
        ocr_confidence=ocr_confidence,
        latency_ms=latency_ms,
        ocr_ms=ocr_ms,
        llm_ms=llm_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=None if cost_usd is None else Decimal(str(cost_usd)),
        safety_blocked=safety_blocked,
    )
    session.add(event)
    await session.flush()
    return event.id


async def get_check_event(session: AsyncSession, check_id: uuid.UUID) -> CheckEvent | None:
    """Return a privacy-safe check event by id for post-check metadata flows."""

    return await session.get(CheckEvent, check_id)


def _validate_check_event_metadata(
    *,
    input_type: str,
    language: str,
    status: str,
    rule_ids: list[str],
    knowledge_card_ids: list[str],
    reviewed_case_ids: list[str],
    retrieval_mode: str | None,
    retrieval_status: str | None,
    router_status: str | None,
    kb_version: str | None,
    error_class: str | None,
) -> None:
    if input_type not in CHECK_EVENT_INPUT_TYPES:
        raise ValueError(f"Unsupported input_type: {input_type}")
    if language not in CHECK_EVENT_LANGUAGES:
        raise ValueError(f"Unsupported language: {language}")
    if status not in CHECK_EVENT_STATUSES:
        raise ValueError(f"Unsupported check status: {status}")
    for rule_id in rule_ids:
        if not RULE_ID_RE.fullmatch(rule_id):
            raise ValueError(f"Unsupported rule_id: {rule_id}")
    for knowledge_id in [*knowledge_card_ids, *reviewed_case_ids]:
        if not RULE_ID_RE.fullmatch(knowledge_id):
            raise ValueError(f"Unsupported knowledge metadata id: {knowledge_id}")
    if retrieval_mode is not None and retrieval_mode not in RETRIEVAL_MODES:
        raise ValueError(f"Unsupported retrieval_mode: {retrieval_mode}")
    if retrieval_status is not None and retrieval_status not in RETRIEVAL_STATUSES:
        raise ValueError(f"Unsupported retrieval_status: {retrieval_status}")
    if router_status is not None and router_status not in ROUTER_STATUSES:
        raise ValueError(f"Unsupported router_status: {router_status}")
    if kb_version is not None and not VERSION_RE.fullmatch(kb_version):
        raise ValueError(f"Unsupported kb_version: {kb_version}")
    if error_class is not None and not ERROR_CLASS_RE.fullmatch(error_class):
        raise ValueError(f"Unsupported error_class: {error_class}")


async def record_feedback(
    session: AsyncSession,
    *,
    check_id: uuid.UUID,
    usefulness: str,
    next_action: str | None = None,
) -> None:
    """Store categorical feedback for a completed check."""

    if usefulness not in USEFULNESS_VALUES:
        raise ValueError(f"Unsupported usefulness value: {usefulness}")
    if next_action is not None and next_action not in NEXT_ACTION_VALUES:
        raise ValueError(f"Unsupported next_action value: {next_action}")

    # Upsert on the check_id primary key: a user can revise their answer (tap a
    # different action button) without hitting a duplicate-key IntegrityError.
    row = await session.get(Feedback, check_id)
    if row is None:
        session.add(
            Feedback(
                check_id=check_id, usefulness=usefulness, next_action=next_action, ts=_utcnow()
            )
        )
    else:
        row.usefulness = usefulness
        if next_action is not None:
            row.next_action = next_action
        row.ts = _utcnow()
    await session.flush()


async def get_usage(
    session: AsyncSession, *, user_key: str, scope: str = "user", day: date | None = None
) -> int:
    """Return today's (or ``day``'s) check count for ``(user_key, scope)``."""

    _validate_scope(scope)
    row = await session.get(RateLimit, (user_key, scope, day or _utcnow().date()))
    return row.count if row else 0


async def increment_usage(
    session: AsyncSession, *, user_key: str, scope: str = "user", day: date | None = None
) -> int:
    """Increment and return the daily check count for ``(user_key, scope)``.

    On PostgreSQL this is a single atomic ``INSERT ... ON CONFLICT DO UPDATE`` so
    two concurrent checks from the same user can't lose an increment (a plain
    read-modify-write races). SQLite (unit tests only) keeps the simple path.
    """

    _validate_scope(scope)
    day = day or _utcnow().date()

    if session.bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = (
            pg_insert(RateLimit)
            .values(user_key=user_key, scope=scope, day=day, count=1)
            .on_conflict_do_update(
                index_elements=["user_key", "scope", "day"],
                set_={"count": RateLimit.count + 1},
            )
            .returning(RateLimit.count)
        )
        return (await session.execute(stmt)).scalar_one()

    row = await session.get(RateLimit, (user_key, scope, day))
    if row is None:
        row = RateLimit(user_key=user_key, scope=scope, day=day, count=1)
        session.add(row)
    else:
        row.count += 1
    await session.flush()
    return row.count


async def refund_usage(
    session: AsyncSession, *, user_key: str, scope: str = "user", day: date | None = None
) -> None:
    """Return one daily slot consumed by a non-billable check.

    ``increment_usage`` reserves a slot up front (so concurrent checks can't race
    past the limit). When the check then fails for a reason that isn't a real
    completion — empty input, unreadable image, provider timeout/error, or an
    over-limit rejection — the slot is given back here so a transient fault or a
    stray empty message doesn't burn the user's daily quota. The atomic
    ``count > 0`` guard keeps the counter from going negative under concurrency.
    """

    _validate_scope(scope)
    day = day or _utcnow().date()
    await session.execute(
        update(RateLimit)
        .where(
            RateLimit.user_key == user_key,
            RateLimit.scope == scope,
            RateLimit.day == day,
            RateLimit.count > 0,
        )
        .values(count=RateLimit.count - 1)
    )
    await session.flush()


def _validate_scope(scope: str) -> None:
    if scope not in RATE_LIMIT_SCOPES:
        raise ValueError(f"Unsupported rate-limit scope: {scope}")


async def delete_user_data(session: AsyncSession, *, user_key: str) -> None:
    """Erase every row for ``user_key`` and write a deletion-log entry.

    Feedback has no ``user_key`` of its own, so its rows are removed via the
    user's check ids before the check events themselves are deleted.
    """

    result = await session.execute(select(CheckEvent.id).where(CheckEvent.user_key == user_key))
    check_ids = result.scalars().all()
    if check_ids:
        await session.execute(delete(Feedback).where(Feedback.check_id.in_(check_ids)))
    await session.execute(delete(StorySubmission).where(StorySubmission.user_key == user_key))
    await session.execute(delete(CheckEvent).where(CheckEvent.user_key == user_key))
    await session.execute(delete(Consent).where(Consent.user_key == user_key))
    await session.execute(delete(RateLimit).where(RateLimit.user_key == user_key))
    now = _utcnow()
    session.add(
        DeletionLog(
            user_key=_deletion_audit_key(user_key),
            requested_ts=now,
            completed_ts=now,
        )
    )
    await session.flush()


def _deletion_audit_key(user_key: str) -> str:
    return hashlib.sha256(f"deletion-log:{user_key}".encode()).hexdigest()[:32]
