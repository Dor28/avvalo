"""R4 Scam Pulse and feedback-as-labels acceptance tests."""

import re
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.data.models import CheckEvent, Feedback
from app.obs.pulse import collect_labels, collect_pulse, render_labels, render_pulse
from app.tools import metrics as metrics_cli


async def test_monthly_pulse_has_exact_family_language_face_counts(session) -> None:
    session.add_all(
        [
            _event(
                month=5,
                user_key="private-previous-family",
                face="family",
                language="ru",
                rule_ids=["fs.credential.otp", "fs.urgency.deadline"],
            ),
            _event(
                month=5,
                user_key="private-previous-merchant",
                face="merchants",
                language="uz_latn",
                rule_ids=[],
                no_signal=True,
            ),
            _event(
                month=6,
                user_key="private-current-credential",
                face="family",
                language="ru",
                rule_ids=["fs.credential.otp", "fs.credential.secret_docs"],
            ),
            _event(
                month=6,
                user_key="private-current-urgency",
                face="family",
                language="uz_latn",
                rule_ids=["fs.urgency.deadline"],
            ),
            _event(
                month=6,
                user_key="private-current-amount",
                face="merchants",
                language="ru",
                rule_ids=["sg.amount.overpay"],
            ),
            _event(
                month=6,
                user_key="private-current-no-signal",
                face="family",
                language="ru",
                rule_ids=[],
                no_signal=True,
            ),
        ]
    )
    await session.flush()

    report = await collect_pulse(session, month="2026-06")
    rows = {
        (row["family"], row["language"], row["face"]): (
            row["count"],
            row["previous_count"],
            row["delta"],
        )
        for row in report["breakdowns"]
    }

    assert report["total_checks"] == 4
    assert report["previous_total_checks"] == 2
    assert report["total_delta"] == 2
    assert report["no_signal_count"] == 1
    assert report["no_signal_rate"] == 0.25
    # Two credential rules in one check count as one family occurrence.
    assert rows[("credential_theft", "ru", "family")] == (1, 1, 0)
    assert rows[("urgency_secrecy", "uz_latn", "family")] == (1, 0, 1)
    assert rows[("urgency_secrecy", "ru", "family")] == (0, 1, -1)
    assert rows[("amount_mismatch", "ru", "merchants")] == (1, 0, 1)

    rendered = render_pulse(report)
    assert "Total checks: 4" in rendered
    assert "Month-over-month: +2 (+100.0%)" in rendered
    assert "credential_theft | ru | family | 1 | 1 | +0" in rendered


async def test_feedback_labels_flag_low_usefulness_rules_against_baseline(session) -> None:
    private_keys: list[str] = []
    private_ids: list[str] = []
    for index in range(10):
        check_id = uuid4()
        user_key = f"private-label-user-{index}"
        private_keys.append(user_key)
        private_ids.append(str(check_id))
        low_rule = index < 5
        usefulness = "yes" if index == 0 or not low_rule else "no"
        next_action = "continue" if low_rule and index > 0 else "verify"
        session.add(
            CheckEvent(
                id=check_id,
                user_key=user_key,
                face="family",
                ts=datetime(2026, 6, 10 + index, tzinfo=UTC),
                input_type="text",
                language="ru",
                rule_ids=["fs.credential.otp" if low_rule else "fs.urgency.deadline"],
                no_signal=False,
                status="ok",
            )
        )
        session.add(
            Feedback(
                check_id=check_id,
                usefulness=usefulness,
                next_action=next_action,
                ts=datetime(2026, 6, 10 + index, tzinfo=UTC),
            )
        )
    await session.flush()

    report = await collect_labels(session, since=datetime(2026, 6, 1, tzinfo=UTC))
    by_rule = {row["rule_id"]: row for row in report["rules"]}

    assert report["labeled_checks"] == 10
    assert report["useful_checks"] == 6
    assert report["overall_useful_rate"] == 0.6
    assert report["overall_next_actions"] == {"continue": 4, "verify": 6}
    assert by_rule["fs.credential.otp"] == {
        "rule_id": "fs.credential.otp",
        "family": "credential_theft",
        "responses": 5,
        "useful": 1,
        "useful_rate": 0.2,
        "gap_from_baseline": 0.4,
        "candidate": True,
        "next_actions": {"continue": 4, "verify": 1},
    }
    assert by_rule["fs.urgency.deadline"]["candidate"] is False

    rendered = render_labels(report)
    assert "fs.credential.otp | credential_theft | 5 | 1 | 20.0% | +40.0% | review" in rendered
    assert "fs.credential.otp | continue | 4 | 80.0% | 4 | 40.0% | +40.0%" in rendered
    assert not re.search(r"\b[0-9a-f]{8}-[0-9a-f-]{27,36}\b", rendered, re.IGNORECASE)
    for private_value in [*private_keys, *private_ids]:
        assert private_value not in rendered
    assert "user_key" not in rendered
    assert "check_id" not in rendered


async def test_metrics_cli_writes_pulse_and_prints_labels(session, tmp_path, capsys) -> None:
    check_id = uuid4()
    session.add(
        _event(
            month=6,
            user_key="cli-private-user",
            face="family",
            language="ru",
            rule_ids=["fs.credential.otp"],
            event_id=check_id,
        )
    )
    session.add(
        Feedback(
            check_id=check_id,
            usefulness="yes",
            next_action="verify",
            ts=datetime(2026, 6, 15, tzinfo=UTC),
        )
    )
    await session.commit()
    factory = async_sessionmaker(session.bind, expire_on_commit=False)

    assert (
        await metrics_cli.run(
            ["pulse", "--month", "2026-06"],
            session_factory=factory,
            output_dir=tmp_path,
        )
        == 0
    )
    output_path = tmp_path / "pulse_2026-06.md"
    assert output_path.exists()
    assert "Total checks: 1" in output_path.read_text(encoding="utf-8")

    assert (
        await metrics_cli.run(
            ["labels", "--since", "2026-06-01"],
            session_factory=factory,
        )
        == 0
    )
    stdout = capsys.readouterr().out
    assert "pulse_2026-06.md" in stdout
    assert "Overall useful rate: 100.0%" in stdout
    assert "cli-private-user" not in stdout


def _event(
    *,
    month: int,
    user_key: str,
    face: str,
    language: str,
    rule_ids: list[str],
    no_signal: bool = False,
    event_id=None,
) -> CheckEvent:
    return CheckEvent(
        id=event_id or uuid4(),
        user_key=user_key,
        face=face,
        ts=datetime(2026, month, 15, tzinfo=UTC),
        input_type="text",
        language=language,
        rule_ids=rule_ids,
        no_signal=no_signal,
        status="no_signal" if no_signal else "ok",
    )
