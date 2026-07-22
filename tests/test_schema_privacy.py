"""Schema, privacy, and repository contract tests."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.data import repo
from app.data.models import Base, DeletionLog, StorySubmission
from app.privacy.user_key import derive_user_key

# Any column whose name hints at stored user content breaks the privacy promise.
CONTENT_TOKENS = (
    "content",
    "message",
    "body",
    "caption",
    "raw_text",
    "ocr_text",
    "snippet",
    "url",
    "username",
    "file_id",
    "payload",
    "prompt",
    "image",
    "name",
    "text",
)

EXPECTED_TABLES = {
    "consent",
    "check_event",
    "feedback",
    "rate_limit",
    "deletion_log",
    "story_submission",
    "url_blocklist",
}
# Legacy exception: intake is disabled, but old rows remain deletable/retained.
ALLOWED_CONTENT_COLUMNS = {"story_submission.minimized_text"}


def test_expected_tables_present() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_no_content_columns_anywhere() -> None:
    offenders = [
        f"{table.name}.{column.name}"
        for table in Base.metadata.tables.values()
        for column in table.columns
        if any(token in column.name.lower() for token in CONTENT_TOKENS)
        and f"{table.name}.{column.name}" not in ALLOWED_CONTENT_COLUMNS
    ]
    assert not offenders, f"content-like columns are forbidden: {offenders}"
    assert {
        f"{table.name}.{column.name}"
        for table in Base.metadata.tables.values()
        for column in table.columns
    } >= ALLOWED_CONTENT_COLUMNS


def test_user_key_is_pseudonymous_and_stable() -> None:
    key = derive_user_key(123456789, secret="unit-secret")

    assert key == derive_user_key("123456789", secret="unit-secret")  # int/str agree
    assert len(key) == 32
    assert "123456789" not in key
    assert derive_user_key(123456789, secret="rotated-secret") != key  # rotation changes keys


async def test_repo_creates_consent_and_event_rows(session) -> None:
    await repo.upsert_consent(
        session,
        user_key="u1",
        notice_version="2026-06-24-v1",
        language="ru",
    )
    check_id = await repo.record_check_event(
        session,
        user_key="u1",
        input_type="text",
        language="ru",
        status="ok",
        rule_ids=["fs.credential.otp"],
        latency_ms=12,
    )
    await session.commit()

    consent = await repo.get_consent(session, user_key="u1")
    assert consent is not None
    assert consent.language == "ru"
    assert isinstance(check_id, uuid.UUID)


async def test_check_event_metadata_values_are_categorical(session) -> None:
    with pytest.raises(ValueError):
        await repo.record_check_event(
            session,
            user_key="u1",
            input_type="text",
            language="ru",
            status="ok",
            error_class="+998 90 123 45 67",
        )

    with pytest.raises(ValueError):
        await repo.record_check_event(
            session,
            user_key="u1",
            input_type="text",
            language="ru",
            status="ok",
            rule_ids=["https://example.com"],
        )


async def test_delete_user_data_removes_every_row(session) -> None:
    await repo.upsert_consent(
        session,
        user_key="u1",
        notice_version="v",
        language="ru",
    )
    check_id = await repo.record_check_event(
        session,
        user_key="u1",
        input_type="text",
        language="ru",
        status="ok",
    )
    await repo.record_feedback(session, check_id=check_id, usefulness="yes", next_action="verify")
    session.add(
        StorySubmission(
            id=uuid.uuid4(),
            user_key="u1",
            language="ru",
            minimized_text="Legacy minimized story",
            status="submitted",
            created_ts=datetime.now(UTC),
        )
    )
    await repo.increment_usage(session, user_key="u1", scope="user")
    await session.commit()

    await repo.delete_user_data(session, user_key="u1")
    await session.commit()

    assert await repo.get_consent(session, user_key="u1") is None
    assert await repo.get_usage(session, user_key="u1", scope="user") == 0
    stories = (await session.execute(select(StorySubmission))).scalars().all()
    assert stories == []
    deletion_log = (await session.execute(select(DeletionLog))).scalar_one()
    assert deletion_log.user_key != "u1"
    assert len(deletion_log.user_key) == 32
