"""R2 scam-library route and content tests."""

import ast
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.web import routes
from app.web.app import create_app
from app.web.content import available_languages, scam_slugs, sitemap_articles

REPO_ROOT = Path(__file__).resolve().parents[1]


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


def test_scam_library_index_is_cacheable_and_hidden_drafts_stay_empty() -> None:
    client = TestClient(create_app(settings=_settings()))

    response = client.get("/scams?language=ru")

    assert response.status_code == 200
    assert "max-age=86400" in response.headers["cache-control"]
    assert routes.WEB_COPY["ru"]["scams_empty"] in response.text
    assert "/scams/credential_theft" not in response.text
    assert 'hreflang="ru"' in response.text
    assert 'hreflang="uz-Latn"' in response.text
    assert 'hreflang="uz-Cyrl"' in response.text


def test_unpublished_scam_pages_404_outside_debug() -> None:
    client = TestClient(create_app(settings=_settings()))

    response = client.get("/scams/credential_theft?language=ru")

    assert response.status_code == 404


def test_debug_renders_every_scam_slug_in_available_languages() -> None:
    client = TestClient(create_app(settings=_settings(), debug=True))

    for slug in scam_slugs():
        assert {"ru", "uz_latn"} <= set(available_languages(slug))
        for language in available_languages(slug):
            response = client.get(f"/scams/{slug}?language={language}")
            assert response.status_code == 200, f"{slug=} {language=}"
            assert routes.WEB_COPY[language]["scams_cta"] in response.text
            assert f"/scams/{slug}?language=ru" in response.text
            assert f"/scams/{slug}?language=uz_latn" in response.text
            assert 'hreflang="ru"' in response.text
            assert 'hreflang="uz-Latn"' in response.text


def test_missing_translation_falls_back_with_notice() -> None:
    client = TestClient(create_app(settings=_settings(), debug=True))

    response = client.get("/scams/credential_theft?language=uz_cyrl")

    assert response.status_code == 200
    assert routes.WEB_COPY["uz_cyrl"]["scams_fallback"] in response.text
    assert routes.WEB_COPY["uz_cyrl"]["scams_cta"] in response.text


def test_sitemap_lists_published_pages_only() -> None:
    client = TestClient(create_app(settings=_settings()))

    assert sitemap_articles() == []
    response = client.get("/sitemap.xml")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    assert "max-age=86400" in response.headers["cache-control"]
    assert "<urlset" in response.text
    assert "<loc>" not in response.text


def test_scam_content_has_ru_and_uz_latn_drafts_for_every_family_slug() -> None:
    for slug in scam_slugs():
        for language in ("ru", "uz_latn"):
            path = REPO_ROOT / "content" / "scams" / language / f"{slug}.md"
            assert path.exists(), f"missing {language} draft for {slug}"
            text = path.read_text(encoding="utf-8")
            assert "published: false" in text
            assert "## " in text


def test_web_content_loader_does_not_import_engine_modules() -> None:
    tree = ast.parse((REPO_ROOT / "app" / "web" / "content.py").read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)

    assert not [name for name in imports if name == "app.engine" or name.startswith("app.engine.")]
