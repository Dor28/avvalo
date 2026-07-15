"""T3 — consent gate and UI-text completeness tests."""

from app.bot.texts import DEFAULT_LANGUAGE, LANGUAGE_LABELS, LANGUAGES, TEXTS, entry_text, t
from app.config import Settings
from app.data import repo
from app.privacy.consent import grant_consent, is_consent_current

NOTICE = "2026-06-24-v1"
R3_NOTICE = "2026-07-07-v2"


def _settings(**overrides) -> Settings:
    values = {
        "telegram_token": "token",
        "database_url": "postgresql+asyncpg://avvalo:avvalo@localhost:5432/avvalo",
        "app_hmac_secret": "test-hmac-secret",
        "llm_base_url": "http://localhost:11434/v1",
        "llm_api_key": "ollama",
        "llm_model": "qwen2.5:7b-instruct",
        "web_session_secret": "test-web-session-secret",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_languages_are_the_three_supported() -> None:
    assert LANGUAGES == ("uz_latn", "uz_cyrl", "ru")
    assert DEFAULT_LANGUAGE in LANGUAGES


def test_every_text_is_translated_in_every_language() -> None:
    for key, table in TEXTS.items():
        for language in LANGUAGES:
            assert table.get(language), f"text '{key}' missing translation for {language}"


def test_language_labels_cover_all_languages() -> None:
    for language in LANGUAGES:
        assert LANGUAGE_LABELS.get(language)


def test_t_falls_back_to_default_language() -> None:
    assert t("ready", "xx") == t("ready", DEFAULT_LANGUAGE)


def test_start_intro_is_short_and_explains_the_flow() -> None:
    intro = t("start_intro", DEFAULT_LANGUAGE)
    assert "Как пользоваться" in intro
    assert "1." in intro and "2." in intro and "3." in intro
    assert "ситуацию, а не человека" in intro
    assert len(intro) < 700


def test_privacy_notice_includes_story_capture_exception() -> None:
    for language in LANGUAGES:
        assert t("privacy_story_notice", language) in t("privacy_notice", language)
        assert t("privacy_story_notice", language) in t("privacy", language)


def test_face_entry_text_can_target_merchants() -> None:
    assert "покупателя" in entry_text("merchants", "ru").lower()
    assert entry_text("unknown_face", "ru") == t("ready", "ru")


def test_is_consent_current_rejects_missing_or_stale() -> None:
    assert is_consent_current(None, NOTICE) is False


async def test_grant_consent_writes_current_version(session) -> None:
    await grant_consent(
        session,
        user_key="u1",
        face="family",
        language="ru",
        notice_version=NOTICE,
    )
    await session.commit()

    consent = await repo.get_consent(session, user_key="u1", face="family")
    assert consent is not None
    assert consent.notice_version == NOTICE
    assert consent.language == "ru"
    assert is_consent_current(consent, NOTICE) is True
    assert is_consent_current(consent, "2099-01-01-v9") is False


async def test_r3_notice_bump_forces_reconsent(session) -> None:
    settings = _settings()
    assert settings.notice_version == R3_NOTICE
    await grant_consent(
        session,
        user_key="u-r3",
        face="family",
        language="ru",
        notice_version=NOTICE,
    )
    await session.commit()

    consent = await repo.get_consent(session, user_key="u-r3", face="family")
    assert is_consent_current(consent, settings.notice_version) is False
