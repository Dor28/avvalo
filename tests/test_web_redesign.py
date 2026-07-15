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


def test_public_flow_uses_the_minimal_shell_without_duplicate_explainers() -> None:
    client = TestClient(create_app())

    landing = client.get("/?language=ru")
    checker = client.get("/check?language=ru")

    assert 'class="landing-visual"' not in landing.text
    assert 'class="preview-card"' not in landing.text
    assert 'class="workflow-list"' not in checker.text
    assert 'class="trust-list"' not in checker.text
    assert 'class="check-summary"' in checker.text
    assert 'class="attachment-panel"' in checker.text
    assert 'class="result-meta"' not in checker.text


def test_consumer_copy_leads_with_the_check_instead_of_family_branding() -> None:
    client = TestClient(create_app())
    localized_copy = [
        (
            "uz_latn",
            "Oilalar uchun",
            "Oila himoyasi",
            "Xabar tekshiruvi",
            "Xabardan tekshiruv rejasigacha",
        ),
        (
            "uz_cyrl",
            "Оилалар учун",
            "Оила ҳимояси",
            "\u0425\u0430\u0431\u0430\u0440 \u0442\u0435\u043a\u0448\u0438\u0440\u0443\u0432\u0438",
            (
                "\u0425\u0430\u0431\u0430\u0440\u0434\u0430\u043d "
                "\u0442\u0435\u043a\u0448\u0438\u0440\u0443\u0432 "
                "\u0440\u0435\u0436\u0430\u0441\u0438\u0433\u0430\u0447\u0430"
            ),
        ),
        (
            "ru",
            "Для семей",
            "Защита семьи",
            "Проверка сообщения",
            "От сообщения к плану проверки",
        ),
    ]

    for language, old_audience, old_name, new_name, workflow in localized_copy:
        landing = client.get(f"/?language={language}")
        checker = client.get(f"/check?language={language}")

        assert landing.status_code == 200
        assert checker.status_code == 200
        assert old_audience not in landing.text
        assert old_audience not in checker.text
        assert old_name not in landing.text
        assert old_name not in checker.text
        assert new_name in checker.text
        assert workflow in landing.text


def test_check_page_exposes_localized_navigation_and_busy_state() -> None:
    response = TestClient(create_app()).get("/check?language=ru")

    assert response.status_code == 200
    assert 'aria-label="Разделы"' in response.text
    assert 'aria-label="Как это работает"' in response.text
    assert 'aria-label="Доверие"' in response.text
    assert 'aria-current="page"' in response.text
    assert 'data-busy-label="Проверяем..."' in response.text
    assert 'class="skip-link"' in response.text
