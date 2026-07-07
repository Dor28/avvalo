"""R2 - public scam education pages."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.web.app import create_app
from app.web.content import available_languages, scam_slugs


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


def test_content_loader_does_not_depend_on_the_engine() -> None:
    source = Path("app/web/content.py").read_text(encoding="utf-8")

    assert "app.engine" not in source


def test_every_family_slug_has_uzbek_latin_and_russian_drafts() -> None:
    slugs = scam_slugs()

    assert slugs == (
        "credential_theft",
        "urgency_secrecy",
        "authority_impersonation",
        "upfront_payment",
        "verification_avoidance",
        "implausible_promise",
        "suspicious_link_qr",
    )
    for slug in slugs:
        assert available_languages(slug) == ("uz_latn", "ru")


def test_debug_routes_render_every_draft_language() -> None:
    client = TestClient(create_app(settings=_settings(), debug=True))

    index = client.get("/scams?language=uz_latn")
    assert index.status_code == 200
    assert "/scams/credential_theft?language=uz_latn" in index.text
    assert 'hreflang="ru"' in index.text

    for slug in scam_slugs():
        for language in available_languages(slug):
            response = client.get(f"/scams/{slug}?language={language}")
            assert response.status_code == 200
            assert "Avvalo" in response.text
            assert "published:" not in response.text
            assert 'rel="alternate"' in response.text


def test_missing_translation_falls_back_in_debug() -> None:
    client = TestClient(create_app(settings=_settings(), debug=True))

    response = client.get("/scams/credential_theft?language=uz_cyrl")

    assert response.status_code == 200
    assert "мавжуд таржима" in response.text
    assert "Kod va maxfiy" in response.text


def test_unpublished_pages_are_hidden_outside_debug() -> None:
    client = TestClient(create_app(settings=_settings()))

    page = client.get("/scams/credential_theft?language=uz_latn")
    index = client.get("/scams?language=ru")

    assert page.status_code == 404
    assert index.status_code == 200
    assert index.headers["cache-control"].startswith("public")
    assert "Материалы пока на проверке" in index.text


def test_sitemap_lists_only_published_pages() -> None:
    client = TestClient(create_app(settings=_settings(), debug=True))

    response = client.get("/sitemap.xml")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert "<urlset" in response.text
    assert "/scams/credential_theft" not in response.text
