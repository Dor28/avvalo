"""T3 — consent gate and UI-text completeness tests."""

from app.bot.texts import DEFAULT_LANGUAGE, LANGUAGE_LABELS, LANGUAGES, TEXTS, entry_text, t
from app.data import repo
from app.privacy.consent import grant_consent, is_consent_current

NOTICE = "2026-06-24-v1"


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


def test_face_entry_text_can_target_seller_guard() -> None:
    assert "покупателя" in entry_text("seller_guard", "ru").lower()
    assert entry_text("unknown_face", "ru") == t("ready", "ru")


def test_is_consent_current_rejects_missing_or_stale() -> None:
    assert is_consent_current(None, NOTICE) is False


async def test_grant_consent_writes_current_version(session) -> None:
    await grant_consent(
        session,
        user_key="u1",
        face="family_shield",
        language="ru",
        notice_version=NOTICE,
    )
    await session.commit()

    consent = await repo.get_consent(session, user_key="u1", face="family_shield")
    assert consent is not None
    assert consent.notice_version == NOTICE
    assert consent.language == "ru"
    assert is_consent_current(consent, NOTICE) is True
    assert is_consent_current(consent, "2099-01-01-v9") is False
