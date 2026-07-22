"""Retention cleanup jobs for privacy-safe tables and legacy story rows.

Active product paths store only pseudonymous metadata. The mapped legacy story
table remains covered here until a separately authorized purge removes it.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.data.models import CheckEvent, Consent, DeletionLog, Feedback, RateLimit, StorySubmission

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetentionPolicy:
    """TTL windows for active metadata and rejected legacy stories."""

    check_event_days: int = 90
    feedback_days: int = 90
    consent_days: int = 365
    rate_limit_hours: int = 48
    deletion_log_days: int = 365
    story_rejected_days: int = 30


@dataclass(frozen=True)
class RetentionResult:
    """Deleted row counts by table."""

    check_events: int = 0
    feedback: int = 0
    consent: int = 0
    rate_limits: int = 0
    deletion_logs: int = 0
    stories: int = 0

    def asdict(self) -> dict[str, int]:
        """Return a plain dict for logs, tests, and CLI output."""

        return asdict(self)


DEFAULT_POLICY = RetentionPolicy()


async def cleanup_expired(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    policy: RetentionPolicy = DEFAULT_POLICY,
) -> RetentionResult:
    """Delete metadata rows older than the configured TTL windows.

    The caller owns the transaction. This function flushes deletions but does
    not commit, so tests and jobs can decide their own commit/rollback boundary.
    """

    now = _normalize_now(now)
    check_cutoff = now - timedelta(days=policy.check_event_days)
    feedback_cutoff = now - timedelta(days=policy.feedback_days)
    consent_cutoff = now - timedelta(days=policy.consent_days)
    rate_limit_cutoff_day = (now - timedelta(hours=policy.rate_limit_hours)).date()
    deletion_log_cutoff = now - timedelta(days=policy.deletion_log_days)
    story_rejected_cutoff = now - timedelta(days=policy.story_rejected_days)

    # Delete feedback that is either past its own TTL or orphaned by an
    # about-to-be-deleted check. A correlated subquery keeps the expired-check
    # ids in the database instead of materializing them into a Python IN-list
    # (which scales poorly and can blow past the driver's bind-parameter limit).
    expired_check_ids = select(CheckEvent.id).where(CheckEvent.ts < check_cutoff)
    feedback_result = await session.execute(
        delete(Feedback).where(
            or_(
                Feedback.ts < feedback_cutoff,
                Feedback.check_id.in_(expired_check_ids),
            )
        )
    )

    check_result = await session.execute(delete(CheckEvent).where(CheckEvent.ts < check_cutoff))
    consent_result = await session.execute(delete(Consent).where(Consent.ts < consent_cutoff))
    rate_result = await session.execute(
        delete(RateLimit).where(RateLimit.day < rate_limit_cutoff_day)
    )
    deletion_log_result = await session.execute(
        delete(DeletionLog).where(
            or_(
                DeletionLog.completed_ts < deletion_log_cutoff,
                DeletionLog.completed_ts.is_(None)
                & (DeletionLog.requested_ts < deletion_log_cutoff),
            )
        )
    )
    story_result = await session.execute(
        delete(StorySubmission).where(
            StorySubmission.status == "rejected",
            or_(
                StorySubmission.reviewed_ts < story_rejected_cutoff,
                StorySubmission.reviewed_ts.is_(None)
                & (StorySubmission.created_ts < story_rejected_cutoff),
            ),
        )
    )
    await session.flush()

    return RetentionResult(
        check_events=_rowcount(check_result),
        feedback=_rowcount(feedback_result),
        consent=_rowcount(consent_result),
        rate_limits=_rowcount(rate_result),
        deletion_logs=_rowcount(deletion_log_result),
        stories=_rowcount(story_result),
    )


async def run_retention(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    policy: RetentionPolicy = DEFAULT_POLICY,
) -> RetentionResult:
    """Compatibility entry point for the scheduled cleanup job."""

    return await cleanup_expired(session, now=now, policy=policy)


run_cleanup = cleanup_expired
purge_expired = cleanup_expired
cleanup = cleanup_expired


async def run_retention_job(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    policy: RetentionPolicy = DEFAULT_POLICY,
) -> RetentionResult:
    """Run retention in its own session and commit the cleanup."""

    async with session_factory() as session:
        result = await cleanup_expired(session, policy=policy)
        await session.commit()
    LOGGER.info("retention cleanup completed counts=%s", result.asdict())
    return result


def install_retention_job(
    scheduler: AsyncIOScheduler,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    policy: RetentionPolicy = DEFAULT_POLICY,
    hour: int = 3,
    minute: int = 0,
) -> None:
    """Install the daily APScheduler TTL cleanup job."""

    scheduler.add_job(
        run_retention_job,
        "cron",
        args=[session_factory],
        kwargs={"policy": policy},
        hour=hour,
        minute=minute,
        id="retention_cleanup",
        replace_existing=True,
    )


def start_retention_scheduler(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    policy: RetentionPolicy = DEFAULT_POLICY,
) -> AsyncIOScheduler:
    """Create, start, and return the in-process retention scheduler."""

    scheduler = AsyncIOScheduler(timezone="UTC")
    install_retention_job(scheduler, session_factory, policy=policy)
    scheduler.start()
    LOGGER.info("retention scheduler started")
    return scheduler


def _normalize_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(UTC)
    if now.tzinfo is None:
        return now.replace(tzinfo=UTC)
    return now.astimezone(UTC)


def _rowcount(result: Any) -> int:
    rowcount = getattr(result, "rowcount", 0)
    return 0 if rowcount is None or rowcount < 0 else int(rowcount)
