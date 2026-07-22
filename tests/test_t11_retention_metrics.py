"""T11 - retention TTL jobs and privacy-safe metrics export."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select

from app.data import repo
from app.data.models import CheckEvent, Consent, DeletionLog, Feedback, RateLimit, StorySubmission
from app.data.retention import cleanup_expired
from app.obs.metrics import collect_metrics, export_metrics


async def test_retention_deletes_only_expired_metadata_rows(session) -> None:
    now = datetime(2026, 6, 27, 12, 0, tzinfo=UTC)
    old_check_id = uuid4()
    fresh_check_id = uuid4()

    session.add_all(
        [
            CheckEvent(
                id=old_check_id,
                user_key="old",
                face="family",
                ts=now - timedelta(days=91),
                input_type="text",
                language="ru",
                rule_ids=[],
                no_signal=False,
                status="ok",
            ),
            CheckEvent(
                id=fresh_check_id,
                user_key="fresh",
                face="family",
                ts=now - timedelta(days=1),
                input_type="text",
                language="ru",
                rule_ids=[],
                no_signal=False,
                status="ok",
            ),
            Feedback(
                check_id=old_check_id,
                usefulness="yes",
                next_action="verify",
                ts=now - timedelta(days=91),
            ),
            Feedback(
                check_id=fresh_check_id,
                usefulness="partly",
                next_action="delay_stop",
                ts=now - timedelta(days=1),
            ),
            Consent(
                user_key="old",
                face="family",
                notice_version="v1",
                language="ru",
                ts=now - timedelta(days=366),
            ),
            Consent(
                user_key="fresh",
                face="family",
                notice_version="v1",
                language="ru",
                ts=now - timedelta(days=1),
            ),
            RateLimit(
                user_key="old",
                face="family",
                day=(now - timedelta(days=3)).date(),
                count=5,
            ),
            RateLimit(
                user_key="fresh",
                face="family",
                day=now.date(),
                count=1,
            ),
            DeletionLog(
                id=uuid4(),
                user_key="old",
                requested_ts=now - timedelta(days=366),
                completed_ts=now - timedelta(days=366),
            ),
            DeletionLog(
                id=uuid4(),
                user_key="fresh",
                requested_ts=now - timedelta(days=1),
                completed_ts=now - timedelta(days=1),
            ),
            StorySubmission(
                id=uuid4(),
                user_key="old-story",
                face="family",
                language="ru",
                minimized_text="old minimized story",
                status="rejected",
                created_ts=now - timedelta(days=40),
                reviewed_ts=now - timedelta(days=31),
            ),
            StorySubmission(
                id=uuid4(),
                user_key="fresh-story",
                face="family",
                language="ru",
                minimized_text="fresh minimized story",
                status="submitted",
                created_ts=now - timedelta(days=40),
                reviewed_ts=None,
            ),
        ]
    )
    await session.flush()

    result = await cleanup_expired(session, now=now)

    assert result.asdict() == {
        "check_events": 1,
        "feedback": 1,
        "consent": 1,
        "rate_limits": 1,
        "deletion_logs": 1,
        "stories": 1,
    }
    assert await _count(session, CheckEvent) == 1
    assert await _count(session, Feedback) == 1
    assert await _count(session, Consent) == 1
    assert await _count(session, RateLimit) == 1
    assert await _count(session, DeletionLog) == 1
    assert await _count(session, StorySubmission) == 1


async def test_metrics_export_returns_privacy_safe_pitch_numbers(session) -> None:
    await repo.upsert_consent(
        session,
        user_key="activated-1",
        face="family",
        notice_version="v1",
        language="ru",
    )
    await repo.upsert_consent(
        session,
        user_key="activated-2",
        face="family",
        notice_version="v1",
        language="uz_latn",
    )
    ok_check_id = await repo.record_check_event(
        session,
        user_key="activated-1",
        face="family",
        input_type="text",
        language="ru",
        status="ok",
        cost_usd=0.01,
        latency_ms=100,
    )
    await repo.record_check_event(
        session,
        user_key="activated-2",
        face="family",
        input_type="text",
        language="uz_latn",
        status="no_signal",
        no_signal=True,
        cost_usd=0.02,
        latency_ms=200,
    )
    await repo.record_check_event(
        session,
        user_key="activated-2",
        face="family",
        input_type="text",
        language="uz_latn",
        status="llm_error",
        cost_usd=0.00,
        latency_ms=300,
        error_class="LLMProviderError",
    )
    await repo.record_feedback(
        session,
        check_id=ok_check_id,
        usefulness="yes",
        next_action="verify",
    )
    retired_check_id = uuid4()
    session.add(
        CheckEvent(
            id=retired_check_id,
            user_key="retired-merchant",
            face="merchants",
            input_type="text",
            language="ru",
            status="ok",
            rule_ids=["sg.amount.overpay"],
            no_signal=False,
            ts=datetime.now(UTC),
        )
    )
    session.add(
        Feedback(
            check_id=retired_check_id,
            usefulness="no",
            next_action="continue",
            ts=datetime.now(UTC),
        )
    )
    await session.flush()

    summary = await collect_metrics(session)
    exported = await export_metrics(session)

    assert summary["checks"]["total"] == 3
    assert summary["checks"]["completed"] == 2
    assert summary["checks"]["completion_rate"] == 0.6667
    assert summary["activation"]["activated_users"] == 2
    assert summary["activation"]["activation_rate"] == 1.0
    assert summary["cost"]["total_usd"] == 0.03
    assert summary["cost"]["avg_success_usd"] == 0.015
    assert summary["no_signal"]["rate"] == 0.5
    assert summary["breakdowns"]["status"] == {"llm_error": 1, "no_signal": 1, "ok": 1}
    assert summary["feedback"]["usefulness"] == {"yes": 1}
    assert "checks_total=3" in exported
    assert "cost_avg_success_usd=0.015" in exported
    assert "activated-1" not in exported
    assert "user_key" not in exported


async def test_metrics_feedback_breakdowns_respect_window_and_partial_answers(session) -> None:
    now = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)
    fresh_check_id = await repo.record_check_event(
        session,
        user_key="fresh-feedback",
        face="family",
        input_type="text",
        language="ru",
        status="ok",
    )
    old_check_id = await repo.record_check_event(
        session,
        user_key="old-feedback",
        face="family",
        input_type="text",
        language="ru",
        status="ok",
    )
    session.add_all(
        [
            Feedback(
                check_id=fresh_check_id,
                usefulness="yes",
                next_action=None,
                ts=now - timedelta(hours=1),
            ),
            Feedback(
                check_id=old_check_id,
                usefulness="no",
                next_action="continue",
                ts=now - timedelta(days=40),
            ),
        ]
    )
    await session.flush()

    summary = await collect_metrics(session, since=now - timedelta(days=7), until=now)

    assert summary["feedback"]["usefulness"] == {"yes": 1}
    assert summary["feedback"]["next_action"] == {}


async def _count(session, model) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()
