"""T2 — schema, privacy, and repository contract tests."""

import uuid

from app.data import repo
from app.data.models import Base
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

EXPECTED_TABLES = {"consent", "check_event", "feedback", "rate_limit", "deletion_log"}


def test_expected_tables_present() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_no_content_columns_anywhere() -> None:
    offenders = [
        f"{table.name}.{column.name}"
        for table in Base.metadata.tables.values()
        for column in table.columns
        if any(token in column.name.lower() for token in CONTENT_TOKENS)
    ]
    assert not offenders, f"content-like columns are forbidden: {offenders}"


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
        face="family_shield",
        notice_version="2026-06-24-v1",
        language="ru",
    )
    check_id = await repo.record_check_event(
        session,
        user_key="u1",
        face="family_shield",
        input_type="text",
        language="ru",
        status="ok",
        rule_ids=["fs.credential.otp"],
        latency_ms=12,
    )
    await session.commit()

    consent = await repo.get_consent(session, user_key="u1", face="family_shield")
    assert consent is not None
    assert consent.language == "ru"
    assert isinstance(check_id, uuid.UUID)


async def test_delete_user_data_removes_every_row(session) -> None:
    await repo.upsert_consent(
        session,
        user_key="u1",
        face="family_shield",
        notice_version="v",
        language="ru",
    )
    check_id = await repo.record_check_event(
        session,
        user_key="u1",
        face="family_shield",
        input_type="text",
        language="ru",
        status="ok",
    )
    await repo.record_feedback(session, check_id=check_id, usefulness="yes", next_action="verify")
    await repo.increment_usage(session, user_key="u1", face="family_shield")
    await session.commit()

    await repo.delete_user_data(session, user_key="u1")
    await session.commit()

    assert await repo.get_consent(session, user_key="u1", face="family_shield") is None
    assert await repo.get_usage(session, user_key="u1", face="family_shield") == 0
