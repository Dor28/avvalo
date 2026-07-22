"""Consent gate and localized UI-text completeness tests."""

from app.bot.texts import (
    DEFAULT_LANGUAGE,
    LANGUAGE_LABELS,
    LANGUAGES,
    TEXTS,
    entry_text,
    normalize_language,
    t,
)
from app.config import Settings
from app.data import repo
from app.privacy.consent import grant_consent, is_consent_current

NOTICE = "2026-06-24-v1"
PREVIOUS_NOTICE = "2026-07-07-v2"
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


def test_languages_are_the_two_supported() -> None:
    assert LANGUAGES == ("uz_latn", "ru")
    assert DEFAULT_LANGUAGE in LANGUAGES


def test_retired_uzbek_cyrillic_is_no_longer_a_reply_language() -> None:
    assert "uz_cyrl" not in LANGUAGES
    assert "uz_cyrl" not in LANGUAGE_LABELS
    for key, table in TEXTS.items():
        assert "uz_cyrl" not in table, f"text '{key}' still carries a uz_cyrl translation"


def test_legacy_stored_language_falls_back_instead_of_stranding_the_user() -> None:
    # Consent rows written before Uzbek Cyrillic was retired still say uz_cyrl.
    # Those users must keep working, answered in Latin-script Uzbek.
    assert normalize_language("uz_cyrl") == DEFAULT_LANGUAGE
    assert normalize_language(None) == DEFAULT_LANGUAGE
    assert normalize_language("ru") == "ru"
    assert normalize_language("uz_latn") == "uz_latn"


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
    assert "1 час" not in privacy_copy
    assert "saqlanmaydi" in privacy_copy
    assert "не сохраняются" in privacy_copy


def test_story_capture_copy_is_retired() -> None:
    assert not any(key.startswith("story_") for key in TEXTS)
    assert "privacy_story_notice" not in TEXTS


def test_entry_text_uses_the_unified_consumer_copy() -> None:
    assert entry_text("ru") == t("ready", "ru")


def test_is_consent_current_rejects_missing_or_stale() -> None:
    assert is_consent_current(None, NOTICE) is False


async def test_grant_consent_writes_current_version(session) -> None:
    await grant_consent(
        session,
        user_key="u1",
        language="ru",
        notice_version=NOTICE,
    )
    await session.commit()

    consent = await repo.get_consent(session, user_key="u1")
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
        user_key="u-previous-notice",
        language="ru",
        notice_version=PREVIOUS_NOTICE,
    )
    await session.commit()

    consent = await repo.get_consent(session, user_key="u-previous-notice")
    assert is_consent_current(consent, settings.notice_version) is False
