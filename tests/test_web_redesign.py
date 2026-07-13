"""Regression checks for the public web redesign shell."""

import re

from fastapi.testclient import TestClient

from app.web.app import create_app


def test_redesign_assets_are_cache_busted_across_public_pages() -> None:
    client = TestClient(create_app())

    responses = [
        client.get("/?language=uz_latn"),
        client.get("/check?language=uz_latn"),
        client.get("/privacy?language=ru"),
        client.get("/scams?language=uz_latn"),
    ]

    for response in responses:
        assert response.status_code == 200
        assert re.search(r'/static/styles\.css\?v=[0-9a-f]{12}', response.text)
        assert re.search(r'/static/icon-192\.png\?v=[0-9a-f]{12}', response.text)


def test_landing_separates_marketing_from_checker_and_hides_merchants() -> None:
    client = TestClient(create_app())

    landing = client.get("/?language=uz_latn")
    checker = client.get("/check?language=uz_latn")
    merchant = client.get("/merchants?language=uz_latn")

    assert landing.status_code == 200
    assert checker.status_code == 200
    assert merchant.status_code == 200
    assert "<form" not in landing.text
    assert 'href="/check?language=uz_latn"' in landing.text
    assert 'href="/merchants' not in landing.text
    assert 'class="check-form"' in checker.text
    assert 'id="result"' in checker.text
    assert 'value="family"' in checker.text
    assert 'href="/merchants' not in checker.text
    assert 'value="merchants"' in merchant.text
    product_nav = re.search(
        r'<nav class="product-nav".*?</nav>', merchant.text, flags=re.DOTALL
    )
    assert product_nav is not None
    assert 'href="/merchants' not in product_nav.group()


def test_check_page_exposes_localized_navigation_and_busy_state() -> None:
    response = TestClient(create_app()).get("/check?language=ru")

    assert response.status_code == 200
    assert 'aria-label="Разделы"' in response.text
    assert 'aria-label="Как это работает"' in response.text
    assert 'aria-label="Доверие"' in response.text
    assert 'aria-current="page"' in response.text
    assert 'data-busy-label="Проверяем..."' in response.text
    assert 'class="skip-link"' in response.text
