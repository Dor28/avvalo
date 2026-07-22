"""Editorial cases: privacy boundary, publishing flow, admin auth, and UI contracts."""

import asyncio
import re
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.content import (
    EditorialBase,
    EditorialPostDraft,
    create_post,
    list_published_posts,
)
from app.data.models import Base
from app.web.app import create_app
from app.web.editorial_copy import EDITORIAL_COPY

ADMIN_KEY = "editorial-test-key-with-enough-entropy"


def _settings(*, admin_access_key: str | None = ADMIN_KEY) -> Settings:
    return Settings(
        _env_file=None,
        telegram_token="token",
        database_url="sqlite+aiosqlite:///:memory:",
        app_hmac_secret="test-hmac-secret",
        llm_base_url="http://localhost:11434/v1",
        llm_api_key="ollama",
        llm_model="qwen2.5:7b-instruct",
        web_session_secret="test-web-session-secret",
        admin_access_key=admin_access_key,
    )


def _post_data(*, state: str = "published", slug: str = "fake-payment-screenshot") -> dict:
    return {
        "language": "ru",
        "slug": slug,
        "category": "payments",
        "state": state,
        "title_uz_latn": "Soxta to‘lov skrinshoti",
        "summary_uz_latn": "Pul tushmasidan oldin tovarni berish so‘ralgan holat.",
        "article_uz_latn": "Skrinshot pul kelganini isbotlamaydi.\n\nBank ilovasini tekshiring.",
        "title_uz_cyrl": "Сохта тўлов скриншоти",
        "summary_uz_cyrl": "Пул тушмасидан олдин товарни бериш сўралган ҳолат.",
        "article_uz_cyrl": "Скриншот пул келганини исботламайди.\n\nБанк иловасини текширинг.",
        "title_ru": "Когда скрин оплаты не подтверждает перевод",
        "summary_ru": "Покупатель просит отдать товар до фактического зачисления денег.",
        "article_ru": "<script>alert(1)</script>\n\nПроверьте поступление в приложении своего банка.",
    }


@pytest_asyncio.fixture
async def editorial_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(EditorialBase.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def editorial_client():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async def prepare() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await connection.run_sync(EditorialBase.metadata.create_all)

    asyncio.run(prepare())
    factory = async_sessionmaker(engine, expire_on_commit=False)
    with TestClient(create_app(settings=_settings(), session_factory=factory)) as client:
        yield client
    asyncio.run(engine.dispose())


def _login(client: TestClient) -> None:
    response = client.post(
        "/admin/login",
        data={"access_key": ADMIN_KEY, "language": "ru"},
        headers={"Origin": "http://testserver"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/posts?language=ru"
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/admin" in cookie


def test_editorial_schema_is_separate_from_submitted_user_data_schema() -> None:
    assert "editorial_post" not in Base.metadata.tables
    assert set(EditorialBase.metadata.tables) == {"editorial_post"}
    assert "user_key" not in EditorialBase.metadata.tables["editorial_post"].columns


def test_editorial_interface_copy_has_the_same_shape_in_all_languages() -> None:
    expected_keys = set(EDITORIAL_COPY["uz_latn"])
    expected_categories = set(EDITORIAL_COPY["uz_latn"]["categories"])

    for copy in EDITORIAL_COPY.values():
        assert set(copy) == expected_keys
        assert set(copy["categories"]) == expected_categories


async def test_repository_publishes_only_complete_public_posts(editorial_session) -> None:
    await create_post(editorial_session, EditorialPostDraft(**_without_language(_post_data())))
    await create_post(
        editorial_session,
        EditorialPostDraft(**_without_language(_post_data(state="draft", slug="draft-case"))),
    )
    await editorial_session.commit()

    posts = await list_published_posts(editorial_session, language="ru")

    assert [post.slug for post in posts] == ["fake-payment-screenshot"]
    assert posts[0].title == "Когда скрин оплаты не подтверждает перевод"
    assert posts[0].reading_minutes == 1


@pytest.mark.parametrize("slug", ["two--dashes", "with spaces", "../escape"])
async def test_repository_rejects_unsafe_slugs(editorial_session, slug: str) -> None:
    with pytest.raises(ValueError, match="invalid_slug"):
        await create_post(
            editorial_session,
            EditorialPostDraft(**_without_language(_post_data(slug=slug))),
        )


def test_admin_is_disabled_when_no_access_key_is_configured() -> None:
    client = TestClient(create_app(settings=_settings(admin_access_key=None)))

    assert client.get("/admin").status_code == 404
    assert client.get("/admin/login").status_code == 404


def test_blank_admin_access_key_disables_routes() -> None:
    settings = _settings(admin_access_key="")
    assert settings.admin_access_key is None
    assert TestClient(create_app(settings=settings)).get("/admin").status_code == 404


def test_admin_login_fails_closed_and_rejects_cross_site_posts(editorial_client) -> None:
    cross_site = editorial_client.post(
        "/admin/login",
        data={"access_key": ADMIN_KEY, "language": "ru"},
        headers={"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"},
    )
    wrong_key = editorial_client.post(
        "/admin/login",
        data={"access_key": "wrong", "language": "ru"},
        headers={"Origin": "http://testserver"},
    )

    assert cross_site.status_code == 403
    assert wrong_key.status_code == 401
    assert "Неверный ключ" in wrong_key.text
    assert "avvalo_admin_session" not in wrong_key.headers.get("set-cookie", "")


def test_admin_can_publish_edit_and_unpublish_a_trilingual_case(editorial_client) -> None:
    unauthenticated = editorial_client.get("/admin/posts", follow_redirects=False)
    assert unauthenticated.status_code == 303
    assert unauthenticated.headers["location"] == "/admin/login?language=uz_latn"

    _login(editorial_client)
    created = editorial_client.post(
        "/admin/posts",
        data=_post_data(),
        headers={"Origin": "http://testserver"},
        follow_redirects=False,
    )
    assert created.status_code == 303

    listing = editorial_client.get("/cases?language=ru")
    detail = editorial_client.get("/cases/fake-payment-screenshot?language=ru")
    uz_detail = editorial_client.get("/cases/fake-payment-screenshot?language=uz_cyrl")
    admin_listing = editorial_client.get("/admin/posts?language=ru")

    assert "Когда скрин оплаты не подтверждает перевод" in listing.text
    assert "Читать разбор" in listing.text
    assert "Когда скрин оплаты не подтверждает перевод" in detail.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in detail.text
    assert "<script>alert(1)</script>" not in detail.text
    assert "Сохта тўлов скриншоти" in uz_detail.text
    assert "Опубликован" in admin_listing.text

    edit_match = re.search(r'/admin/posts/([0-9a-f-]+)/edit', admin_listing.text)
    assert edit_match is not None
    edit_href = edit_match.group(1)
    updated_data = _post_data(state="draft")
    updated_data["title_ru"] = "Обновлённый черновик"
    updated = editorial_client.post(
        f"/admin/posts/{edit_href}",
        data=updated_data,
        headers={"Origin": "http://testserver"},
        follow_redirects=False,
    )

    assert updated.status_code == 303
    assert editorial_client.get("/cases/fake-payment-screenshot?language=ru").status_code == 404
    assert "Обновлённый черновик" in editorial_client.get("/admin/posts?language=ru").text


def test_admin_rejects_duplicate_slug_without_losing_the_editor(editorial_client) -> None:
    _login(editorial_client)
    first = editorial_client.post(
        "/admin/posts",
        data=_post_data(),
        headers={"Origin": "http://testserver"},
    )
    duplicate = editorial_client.post(
        "/admin/posts",
        data=_post_data(),
        headers={"Origin": "http://testserver"},
    )

    assert first.status_code == 200
    assert duplicate.status_code == 409
    assert "Такой адрес страницы уже используется" in duplicate.text
    assert 'value="fake-payment-screenshot"' in duplicate.text


def test_admin_returns_the_editor_for_an_incomplete_submission(editorial_client) -> None:
    _login(editorial_client)

    response = editorial_client.post(
        "/admin/posts",
        data={"language": "ru", "slug": "incomplete", "category": "payments"},
        headers={"Origin": "http://testserver"},
    )

    assert response.status_code == 400
    assert "Проверьте все поля" in response.text
    assert 'value="incomplete"' in response.text


def test_editorial_assets_and_login_rate_limit_are_declared() -> None:
    nginx = Path("deploy/nginx/templates/avvalo.conf.template").read_text(encoding="utf-8")

    assert "zone=admin_login_posts" in nginx
    assert "location = /admin/login" in nginx
    assert "ADMIN_ACCESS_KEY=" in Path(".env.example").read_text(encoding="utf-8")
    assert "ADMIN_ACCESS_KEY=" in Path("deploy/env.prod.example").read_text(encoding="utf-8")


def _without_language(values: dict) -> dict:
    return {key: value for key, value in values.items() if key != "language"}
