"""Privacy-safe feedback label acceptance tests."""

import re
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.data.models import CheckEvent, Feedback
from app.obs.feedback_labels import collect_labels, render_labels
from app.tools import metrics as metrics_cli


async def test_feedback_labels_flag_low_usefulness_rules_against_baseline(session) -> None:
    private_values: list[str] = []
    for index in range(10):
        check_id = uuid4()
        user_key = f"private-label-user-{index}"
        private_values.extend((user_key, str(check_id)))
        low_rule = index < 5
        usefulness = "yes" if index == 0 or not low_rule else "no"
        next_action = "continue" if low_rule and index > 0 else "verify"
        session.add(
            CheckEvent(
                id=check_id,
                user_key=user_key,
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
    assert by_rule["fs.credential.otp"]["candidate"] is True
    assert by_rule["fs.urgency.deadline"]["candidate"] is False

    rendered = render_labels(report)
    assert "fs.credential.otp | credential_theft | 5 | 1 | 20.0% | +40.0% | review" in rendered
    assert not re.search(r"\b[0-9a-f]{8}-[0-9a-f-]{27,36}\b", rendered, re.IGNORECASE)
    assert all(value not in rendered for value in private_values)
    assert "user_key" not in rendered
    assert "check_id" not in rendered


async def test_metrics_cli_prints_labels_without_private_values(session, capsys) -> None:
    check_id = uuid4()
    session.add(
        CheckEvent(
            id=check_id,
            user_key="cli-private-user",
            ts=datetime(2026, 6, 15, tzinfo=UTC),
            input_type="text",
            language="ru",
            rule_ids=["fs.credential.otp"],
            no_signal=False,
            status="ok",
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
            ["labels", "--since", "2026-06-01"],
            session_factory=factory,
        )
        == 0
    )
    stdout = capsys.readouterr().out
    assert "Overall useful rate: 100.0%" in stdout
    assert "cli-private-user" not in stdout
