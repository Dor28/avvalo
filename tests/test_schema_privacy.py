"""T2 — schema, privacy, and repository contract tests."""

import uuid

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
}
# R3 reviewed exception: opt-in, minimized, founder-reviewed story corpus.
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
        face="family",
        notice_version="2026-06-24-v1",
        language="ru",
    )
    check_id = await repo.record_check_event(
        session,
        user_key="u1",
        face="family",
        input_type="text",
        language="ru",
        status="ok",
        rule_ids=["fs.credential.otp"],
        latency_ms=12,
    )
    await session.commit()

    consent = await repo.get_consent(session, user_key="u1", face="family")
    assert consent is not None
    assert consent.language == "ru"
    assert isinstance(check_id, uuid.UUID)


async def test_check_event_metadata_values_are_categorical(session) -> None:
    with pytest.raises(ValueError):
        await repo.record_check_event(
            session,
            user_key="u1",
            face="family",
            input_type="text",
            language="ru",
            status="ok",
            error_class="+998 90 123 45 67",
        )

    with pytest.raises(ValueError):
        await repo.record_check_event(
            session,
            user_key="u1",
            face="family",
            input_type="text",
            language="ru",
            status="ok",
            rule_ids=["https://example.com"],
        )


async def test_delete_user_data_removes_every_row(session) -> None:
    await repo.upsert_consent(
        session,
        user_key="u1",
        face="family",
        notice_version="v",
        language="ru",
    )
    check_id = await repo.record_check_event(
        session,
        user_key="u1",
        face="family",
        input_type="text",
        language="ru",
        status="ok",
    )
    await repo.record_feedback(session, check_id=check_id, usefulness="yes", next_action="verify")
    await repo.store_story(
        session,
        user_key="u1",
        face="family",
        language="ru",
        raw_text="Murod Karimov asked for SMS kod 123456 and +998 90 123 45 67.",
    )
    await repo.increment_usage(session, user_key="u1", face="family")
    await session.commit()

    await repo.delete_user_data(session, user_key="u1")
    await session.commit()

    assert await repo.get_consent(session, user_key="u1", face="family") is None
    assert await repo.get_usage(session, user_key="u1", face="family") == 0
    stories = (await session.execute(select(StorySubmission))).scalars().all()
    assert stories == []
    deletion_log = (await session.execute(select(DeletionLog))).scalar_one()
    assert deletion_log.user_key != "u1"
    assert len(deletion_log.user_key) == 32


async def test_store_story_reminimizes_raw_text_before_db_write(session) -> None:
    story = await repo.store_story(
        session,
        user_key="story-user",
        face="family",
        language="ru",
        raw_text=(
            "Murod Karimov wrote from +998 90 123 45 67, asked for SMS kod 123456, "
            "sent card 8600 1234 5678 9012 and link https://payme-fake.example/login."
        ),
    )
    await session.commit()

    stored = await session.get(StorySubmission, story.id)
    assert stored is not None
    assert stored.status == "submitted"
    assert "[PHONE]" in stored.minimized_text
    assert "[CARD]" in stored.minimized_text
    assert "[LINK" in stored.minimized_text
    assert "+998" not in stored.minimized_text
    assert "8600" not in stored.minimized_text
    assert "123456" not in stored.minimized_text
    assert "Murod Karimov" not in stored.minimized_text
