"""Unified public web shell, behavior, and cache-policy tests."""

import re

from fastapi.testclient import TestClient

from app.web.app import create_app


def test_redesign_assets_are_cache_busted_across_public_pages() -> None:
    client = TestClient(create_app())

    responses = [
        client.get("/?language=uz_latn"),
        client.get("/check?language=uz_latn"),
        client.get("/privacy?language=ru"),
    ]

    for response in responses:
        assert response.status_code == 200
        assert re.search(r'/static/styles\.css\?v=[0-9a-f]{12}', response.text)
        assert re.search(r'/static/icon-192\.png\?v=[0-9a-f]{12}', response.text)


def test_home_leads_with_the_unified_checker() -> None:
    """The home page IS the checker.

    This deliberately reverses the earlier landing/checker split: a visitor who
    lands on ``/`` must be able to paste a message without a second click.
    ``/check`` stays live for existing links, QR codes and bot deep links.
    """

    client = TestClient(create_app())

    landing = client.get("/?language=uz_latn")
    checker = client.get("/check?language=uz_latn")
    merchant = client.get("/merchants?language=uz_latn", follow_redirects=False)

    assert landing.status_code == 200
    assert checker.status_code == 200
    assert merchant.status_code == 308
    assert merchant.headers["location"] == "/check?language=uz_latn"
    assert 'class="check-form"' in landing.text
    assert 'action="/check"' in landing.text
    assert 'name="face"' not in landing.text
    assert 'id="result"' in landing.text
    assert 'href="/merchants' not in landing.text
    assert 'class="check-form"' in checker.text
    assert 'id="result"' in checker.text
    assert 'name="face"' not in checker.text
    assert 'href="/merchants' not in checker.text
    assert client.get("/scams").status_code == 404
    assert client.get("/sitemap.xml").status_code == 404


def test_home_and_check_share_one_product_shell_and_supported_scope() -> None:
    client = TestClient(create_app())

    landing = client.get("/?language=ru")
    checker = client.get("/check?language=ru")

    for response in (landing, checker):
        assert response.status_code == 200
        assert 'class="composer-card"' in response.text
        assert 'class="use-cases"' in response.text
        assert 'class="trust-list"' in response.text
        assert 'class="outcome-section"' in response.text
        assert 'class="boundary-card"' in response.text
        assert 'class="attachment-grid"' in response.text
        assert 'Скрин оплаты' in response.text
        assert 'Документ или запрос' in response.text
        assert 'class="check-summary"' not in response.text
        assert 'class="field-step"' not in response.text
        assert 'class="result-meta"' not in response.text


def test_consumer_copy_leads_with_the_check_instead_of_family_branding() -> None:
    client = TestClient(create_app())
    localized_copy = [
        (
            "uz_latn",
            "Oilalar uchun",
            "Oila himoyasi",
            "Vaziyat tekshiruvi",
            "To\u2018lov skrinshoti",
        ),
        (
            "ru",
            "Для семей",
            "Защита семьи",
            "Проверка ситуации",
            "Скрин оплаты",
        ),
    ]

    for language, old_audience, old_name, new_name, broad_example in localized_copy:
        landing = client.get(f"/?language={language}")
        checker = client.get(f"/check?language={language}")

        assert landing.status_code == 200
        assert checker.status_code == 200
        assert old_audience not in landing.text
        assert old_audience not in checker.text
        assert old_name not in landing.text
        assert old_name not in checker.text
        assert new_name in landing.text
        assert new_name in checker.text
        assert broad_example in landing.text
        assert broad_example in checker.text


def test_check_page_exposes_localized_flow_and_busy_state() -> None:
    response = TestClient(create_app()).get("/check?language=ru")

    assert response.status_code == 200
    assert 'aria-label="Что можно отправить в Avvalo"' in response.text
    assert 'aria-current="page"' in response.text
    assert 'data-busy-label="Проверяем..."' in response.text
    assert 'data-consent-error="Сначала примите условия конфиденциальности."' in response.text
    assert 'class="skip-link"' in response.text
    assert '>O\u2018z</a>' in response.text
    assert '>RU</a>' in response.text
    assert 'aria-label="Русский"' in response.text
    assert "Avvalo Verify" not in response.text


def test_app_pages_are_never_cached_so_a_deploy_is_visible_immediately() -> None:
    """A returning visitor must not be served the previous deploy.

    These responses used to carry no Cache-Control and no validator at all,
    which lets a browser reuse a stored copy heuristically — the page looks
    unchanged after a deploy, and its stale ?v= URLs pin the old CSS and JS
    too. The retired merchant compatibility redirect must not be cached either.
    """

    client = TestClient(create_app())

    for path in ("/", "/check", "/privacy"):
        response = client.get(f"{path}?language=uz_latn")

        assert response.status_code == 200, path
        assert response.headers["cache-control"] == "no-store", path

    merchant = client.get("/merchants?language=uz_latn", follow_redirects=False)
    assert merchant.status_code == 308
    assert merchant.headers["cache-control"] == "no-store"


def test_static_assets_stay_cacheable_and_fingerprinted() -> None:
    """no-store applies to pages only; assets rely on the ?v= fingerprint."""

    client = TestClient(create_app())
    home = client.get("/?language=uz_latn")

    match = re.search(r'/static/(check\.js|styles\.css)\?v=([0-9a-f]{12})', home.text)
    assert match is not None

    asset = client.get(f"/static/{match.group(1)}?v={match.group(2)}")
    assert asset.status_code == 200
    assert asset.headers.get("cache-control") != "no-store"
