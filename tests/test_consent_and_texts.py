"""T3 — consent gate and UI-text completeness tests."""

from app.bot.texts import DEFAULT_LANGUAGE, LANGUAGE_LABELS, LANGUAGES, TEXTS, entry_text, t
from app.config import Settings
from app.data import repo
from app.privacy.consent import grant_consent, is_consent_current

NOTICE = "2026-06-24-v1"
R3_NOTICE = "2026-07-07-v2"
CURRENT_NOTICE = "2026-07-22-v3"


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
    assert "O'zbekcha" in intro
    assert "Русский" in intro
    assert "Xabar, rasm yoki vaziyatni yuboring" in intro
    assert "Пришлите сообщение, изображение или опишите ситуацию" in intro
    assert "QR-kod" in intro
    assert "QR-код" in intro
    assert len(intro) < 700


def test_privacy_copy_matches_ephemeral_content_contract() -> None:
    privacy_copy = "\n".join(
        t(key, language) for key in ("privacy_notice", "privacy") for language in LANGUAGES
    )

    assert "1 soat" not in privacy_copy
    assert "1 соат" not in privacy_copy
    assert "1 час" not in privacy_copy
    assert "saqlanmaydi" in privacy_copy
    assert "сақланмайди" in privacy_copy
    assert "не сохраняются" in privacy_copy


def test_story_capture_copy_is_retired() -> None:
    assert not any(key.startswith("story_") for key in TEXTS)
    assert "privacy_story_notice" not in TEXTS


def test_face_entry_text_uses_the_unified_consumer_copy() -> None:
    assert entry_text("family", "ru") == t("ready_family", "ru")
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


async def test_current_notice_bump_forces_reconsent(session) -> None:
    settings = _settings()
    assert settings.notice_version == CURRENT_NOTICE
    await grant_consent(
        session,
        user_key="u-r3",
        face="family",
        language="ru",
        notice_version=R3_NOTICE,
    )
    await session.commit()

    consent = await repo.get_consent(session, user_key="u-r3", face="family")
    assert is_consent_current(consent, settings.notice_version) is False
