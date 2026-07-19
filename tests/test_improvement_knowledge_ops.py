"""T-03/T-04 acceptance: metadata-only gaps, coverage, inventory, and alerts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.data.models import CheckEvent, Feedback
from app.obs.alerts import (
    evaluate_knowledge_availability,
    run_knowledge_availability_alert_job,
)
from app.obs.metrics import collect_metrics, export_metrics
from app.tools.knowledge_gaps import (
    collect_knowledge_gaps,
    render_knowledge_gaps,
)
from app.tools.knowledge_gaps import (
    run as run_gap_cli,
)

NOW = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)


def _event(
    *,
    face: str = "family",
    language: str = "ru",
    cards: list[str] | None = None,
    rules: list[str] | None = None,
    retrieval_status: str = "empty",
    retrieval_mode: str = "none",
    router_status: str = "not_used",
    ts: datetime = NOW,
) -> CheckEvent:
    return CheckEvent(
        id=uuid4(),
        user_key=uuid4().hex,
        face=face,
        ts=ts,
        input_type="text",
        language=language,
        rule_ids=rules or [],
        knowledge_card_ids=cards or [],
        reviewed_case_ids=[],
        retrieval_status=retrieval_status,
        retrieval_mode=retrieval_mode,
        router_status=router_status,
        no_signal=not rules,
        status="no_signal" if not rules else "ok",
        latency_ms=10,
    )


async def test_gap_report_separates_no_match_from_unavailable_and_groups_feedback(
    session,
) -> None:
    found = _event(cards=["family.authority_impersonation"], retrieval_status="ok")
    gap = _event(rules=["fs.credential.otp"])
    outage = _event(retrieval_status="unavailable")
    routed = _event(
        cards=["family.urgency_secrecy"],
        retrieval_status="ok",
        retrieval_mode="router",
        router_status="ok",
    )
    invalid = _event(router_status="invalid_ids")
    session.add_all([found, gap, outage, routed, invalid])
    session.add(
        Feedback(check_id=gap.id, usefulness="no", next_action="not_sure", ts=NOW)
    )
    await session.flush()

    report = await collect_knowledge_gaps(
        session,
        since=NOW - timedelta(days=1),
        until=NOW + timedelta(days=1),
        face="family",
    )
    rendered = render_knowledge_gaps(report)

    coverage = report["coverage"][0]
    assert coverage == {
        "face": "family",
        "language": "ru",
        "checks": 5,
        "found": 2,
        "coverage_rate": 0.4,
        "no_match": 2,
        "unavailable": 1,
    }
    assert report["gaps"] == [
        {
            "face": "family",
            "language": "ru",
            "rule_ids": ["fs.credential.otp"],
            "count": 1,
        }
    ]
    assert report["router_health"] == {
        "mode:none": 4,
        "mode:router": 1,
        "status:invalid_ids": 1,
        "status:ok": 1,
    }
    assert "outage, not a no-match" in rendered
    assert "submitted content is not stored" in rendered
    assert gap.user_key not in rendered
    assert str(gap.id) not in rendered


async def test_gap_report_handles_zero_rows_without_division(session) -> None:
    report = await collect_knowledge_gaps(
        session,
        since=NOW - timedelta(days=1),
        until=NOW,
    )
    rendered = render_knowledge_gaps(report)

    assert report["coverage"] == []
    assert report["gaps"] == []
    assert "No checks in this window." in rendered


async def test_gap_cli_runs_read_only_against_seeded_database(session, capsys) -> None:
    session.add(
        _event(
            cards=["family.authority_impersonation"],
            retrieval_status="ok",
            ts=datetime.now(UTC),
        )
    )
    await session.commit()
    factory = async_sessionmaker(session.bind, expire_on_commit=False)
    settings = SimpleNamespace(knowledge_gap_default_days=7)

    exit_code = await run_gap_cli(
        ["--days", "7"],
        session_factory=factory,
        settings=settings,  # type: ignore[arg-type]
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Avvalo knowledge-gap report" in output
    assert "family/ru: 1/1 found" in output
    assert "submitted content is not stored" in output


async def test_daily_metrics_include_coverage_unavailable_and_card_inventory(session) -> None:
    session.add_all(
        [
            _event(cards=["family.authority_impersonation"], retrieval_status="ok"),
            _event(retrieval_status="empty"),
            _event(retrieval_status="unavailable"),
        ]
    )
    await session.flush()

    summary = await collect_metrics(
        session,
        since=NOW - timedelta(days=1),
        until=NOW + timedelta(days=1),
    )
    exported = await export_metrics(
        session,
        since=NOW - timedelta(days=1),
        until=NOW + timedelta(days=1),
    )

    assert summary["knowledge"]["checks"] == 3
    assert summary["knowledge"]["selected"] == 1
    assert summary["knowledge"]["coverage_rate"] == 0.3333
    assert summary["knowledge"]["unavailable_rate"] == 0.3333
    assert summary["knowledge"]["inventory"]["version"] == "2026-07-15-v1"
    assert summary["knowledge"]["inventory"]["approved_cards"] == {
        "family": 7,
        "merchants": 5,
    }
    assert "knowledge_coverage_rate=0.3333" in exported
    assert "knowledge_unavailable_rate=0.3333" in exported
    assert "kb_version=2026-07-15-v1" in exported
    assert "kb_approved_cards_family=7" in exported


async def test_knowledge_unavailable_alert_fires_above_and_stays_quiet_below(
    session,
) -> None:
    session.add_all(
        [
            _event(retrieval_status="unavailable"),
            _event(retrieval_status="unavailable"),
            _event(retrieval_status="ok", cards=["family.authority_impersonation"]),
            _event(retrieval_status="ok", cards=["family.urgency_secrecy"]),
        ]
    )
    await session.flush()

    above = await evaluate_knowledge_availability(
        session,
        since=NOW - timedelta(minutes=30),
        threshold=0.5,
    )
    below = await evaluate_knowledge_availability(
        session,
        since=NOW - timedelta(minutes=30),
        threshold=0.75,
    )

    assert above.checks == 4
    assert above.rate == 0.5
    assert above.alert is True
    assert below.alert is False


async def test_knowledge_alert_does_not_fire_without_an_outage_at_zero_threshold(
    session,
) -> None:
    session.add(
        _event(
            retrieval_status="ok",
            cards=["family.authority_impersonation"],
        )
    )
    await session.flush()

    availability = await evaluate_knowledge_availability(
        session,
        since=NOW - timedelta(minutes=30),
        threshold=0.0,
    )

    assert availability.rate == 0.0
    assert availability.alert is False


async def test_sustained_unavailable_job_emits_only_above_threshold(session, caplog) -> None:
    now = datetime.now(UTC)
    session.add_all(
        [
            _event(retrieval_status="unavailable", ts=now),
            _event(
                retrieval_status="ok",
                cards=["family.authority_impersonation"],
                ts=now,
            ),
        ]
    )
    await session.commit()
    factory = async_sessionmaker(session.bind, expire_on_commit=False)

    caplog.set_level("ERROR", logger="app.obs.events")
    above = SimpleNamespace(
        knowledge_unavailable_alert_window_minutes=30,
        knowledge_unavailable_alert_threshold=0.5,
    )
    await run_knowledge_availability_alert_job(factory, above)  # type: ignore[arg-type]
    assert "KnowledgeUnavailableSpike" in caplog.text

    caplog.clear()
    below = SimpleNamespace(
        knowledge_unavailable_alert_window_minutes=30,
        knowledge_unavailable_alert_threshold=0.75,
    )
    await run_knowledge_availability_alert_job(factory, below)  # type: ignore[arg-type]
    assert "KnowledgeUnavailableSpike" not in caplog.text
