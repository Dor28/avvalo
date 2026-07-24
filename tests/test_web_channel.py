"""Web-channel parity, privacy boundaries, and abuse-gate tests."""

import logging

from fastapi.testclient import TestClient
from starlette.formparsers import MultiPartParser

from app.config import Settings
from app.engine import CheckResult, CheckStatus, InputType, Language
from app.web import routes
from app.web.abuse import MAX_REQUEST_BODY_BYTES, configure_ephemeral_multipart
from app.web.app import create_app


class FakeSession:
    async def commit(self) -> None:
        return None


class FakeSessionFactory:
    def __call__(self):
        return self

    async def __aenter__(self) -> FakeSession:
        return FakeSession()

    async def __aexit__(self, *_exc) -> None:
        return None


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


def test_web_app_exposes_core_routes() -> None:
    app = create_app(settings=_settings())
    paths = {getattr(route, "path", "") for route in getattr(app, "routes", [])}

    assert "/" in paths
    # Kept only as a compatibility redirect for old bookmarks.
    assert "/merchants" in paths
    assert "/check" in paths
    assert "/privacy" in paths
    assert "/healthz" in paths
    assert "/readyz" in paths
    assert "/scams" not in paths
    assert "/sitemap.xml" not in paths


def test_readiness_fails_closed_without_database_wiring() -> None:
    response = TestClient(create_app(settings=_settings())).get("/readyz")

    assert response.status_code == 503


def test_web_app_does_not_publish_an_openapi_schema() -> None:
    client = TestClient(create_app(settings=_settings()))

    assert client.get("/openapi.json").status_code == 404


def test_multipart_uploads_cannot_roll_accepted_content_to_disk() -> None:
    configure_ephemeral_multipart()

    assert MultiPartParser.spool_max_size > MAX_REQUEST_BODY_BYTES


def test_request_body_is_rejected_before_form_parsing_when_declared_too_large() -> None:
    client = TestClient(create_app(settings=_settings()))

    response = client.post(
        "/check",
        content=b"x",
        headers={
            "Content-Length": str(MAX_REQUEST_BODY_BYTES + 1),
            "Content-Type": "application/octet-stream",
        },
    )

    assert response.status_code == 413
    assert response.headers["cache-control"] == "no-store"


def test_unhandled_route_exception_logs_and_returns_500(caplog) -> None:
    caplog.set_level(logging.ERROR, logger="app.obs.events")
    app = create_app(settings=_settings())

    @app.get("/__test_boom")
    def _boom():
        raise ValueError("unexpected")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/__test_boom")

    assert response.status_code == 500
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "event=app_error" in messages
    assert "'stage': 'web'" in messages
    assert "'error_type': 'ValueError'" in messages


def test_checker_is_localized_and_old_merchants_url_redirects() -> None:
    client = TestClient(create_app(settings=_settings()))

    landing = client.get("/?language=uz_latn")
    family = client.get("/check?language=uz_latn")
    merchants = client.get("/merchants?language=ru", follow_redirects=False)

    assert landing.status_code == 200
    assert family.status_code == 200
    assert merchants.status_code == 308
    assert merchants.headers["location"] == "/check?language=ru"
    # The landing page links to /check; only /check itself posts there.
    assert 'action="/check"' in family.text
    assert 'href="/check?language=uz_latn"' in landing.text
    assert 'name="face"' not in landing.text
    assert 'name="face"' not in family.text
    assert 'name="caption"' not in landing.text
    assert 'name="caption"' not in family.text
    assert "/merchants?language=uz_latn" not in landing.text
    assert "/merchants?language=uz_latn" not in family.text
    assert 'type="radio"' not in family.text


def test_web_reuses_the_shared_engine(monkeypatch) -> None:
    calls = []

    async def fake_run_check(check_input, *args, **kwargs):
        calls.append((check_input, args, kwargs))
        return CheckResult(
            status=CheckStatus.ok,
            text="checked by shared engine",
            language=check_input.language,
            input_type=check_input.input_type,
        )

    monkeypatch.setattr(routes, "run_check", fake_run_check)

    async def fake_ensure_web_consent(*_args, **_kwargs) -> bool:
        return True

    async def fake_reserve_web_ip_limit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(routes, "_ensure_web_consent", fake_ensure_web_consent)
    monkeypatch.setattr(routes, "_reserve_web_ip_limit", fake_reserve_web_ip_limit)
    client = TestClient(create_app(settings=_settings(), session_factory=FakeSessionFactory()))

    response = client.post(
        "/check",
        data={
            "language": "uz_latn",
            "text": "Bank xavfsizlik xizmatidanmiz. SMS kodni yuboring.",
            "consent": "yes",
        },
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "checked by shared engine" in response.text
    assert len(calls) == 1
    check_input, _args, kwargs = calls[0]
    assert check_input.input_type is InputType.text
    assert check_input.language is Language.uz_latn
    assert check_input.raw_text.startswith("Bank xavfsizlik")
    assert kwargs["rate_limit_override"] == 5
    assert kwargs["commit_rate_limit_reservation"] is True
    assert kwargs["session"].__class__ is FakeSession


def test_web_rejects_cross_site_post_before_engine_or_database(monkeypatch) -> None:
    async def fake_run_check(*_args, **_kwargs):
        raise AssertionError("cross-site request must not reach the engine")

    monkeypatch.setattr(routes, "run_check", fake_run_check)
    client = TestClient(create_app(settings=_settings(), session_factory=FakeSessionFactory()))

    response = client.post(
        "/check",
        data={
                        "language": "ru",
            "text": "SMS code",
            "consent": "yes",
        },
        headers={
            "Origin": "https://attacker.example",
            "Sec-Fetch-Site": "cross-site",
        },
    )

    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"


def test_web_accepts_matching_origin(monkeypatch) -> None:
    calls = []

    async def fake_run_check(check_input, *args, **kwargs):
        calls.append(check_input)
        return CheckResult(
            status=CheckStatus.ok,
            text="ok",
            language=check_input.language,
            input_type=check_input.input_type,
        )

    async def fake_ensure_web_consent(*_args, **_kwargs) -> bool:
        return True

    async def fake_reserve_web_ip_limit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(routes, "run_check", fake_run_check)
    monkeypatch.setattr(routes, "_ensure_web_consent", fake_ensure_web_consent)
    monkeypatch.setattr(routes, "_reserve_web_ip_limit", fake_reserve_web_ip_limit)
    client = TestClient(
        create_app(settings=_settings(), session_factory=FakeSessionFactory()),
        base_url="https://avvalo.uz",
    )

    response = client.post(
        "/check",
        data={
                        "language": "ru",
            "text": "SMS code",
            "consent": "yes",
        },
        headers={"Origin": "https://avvalo.uz", "Sec-Fetch-Site": "same-origin"},
    )

    assert response.status_code == 200
    assert len(calls) == 1


def test_https_request_always_sets_secure_session_cookie() -> None:
    client = TestClient(
        create_app(settings=_settings(web_cookie_secure=False)),
        base_url="https://avvalo.uz",
    )

    response = client.get("/check?language=ru")

    assert response.status_code == 200
    assert "Secure" in response.headers["set-cookie"]


def test_web_check_fails_closed_without_session_factory(monkeypatch) -> None:
    async def fake_run_check(*_args, **_kwargs):
        raise AssertionError("miswired web app must not process checks")

    monkeypatch.setattr(routes, "run_check", fake_run_check)
    client = TestClient(create_app(settings=_settings()))

    response = client.post(
        "/check",
        data={
                        "language": "uz_latn",
            "text": "Bank xavfsizlik xizmatidanmiz. SMS kodni yuboring.",
            "consent": "yes",
        },
    )

    assert response.status_code == 503


def test_image_upload_fails_without_turnstile(monkeypatch) -> None:
    async def fake_run_check(*_args, **_kwargs):
        raise AssertionError("image upload must be rejected before run_check")

    async def fake_ensure_web_consent(*_args, **_kwargs) -> bool:
        return True

    monkeypatch.setattr(routes, "run_check", fake_run_check)
    monkeypatch.setattr(routes, "_ensure_web_consent", fake_ensure_web_consent)
    client = TestClient(create_app(settings=_settings(), session_factory=FakeSessionFactory()))

    response = client.post(
        "/check",
        data={
                        "language": "uz_latn",
            "consent": "yes",
        },
        files={"image": ("check.png", b"not-empty", "image/png")},
    )

    assert response.status_code == 400


def test_web_requires_consent_before_reading_upload(monkeypatch) -> None:
    async def fake_ensure_web_consent(*_args, **_kwargs) -> bool:
        return False

    async def fake_read_limited_upload(*_args, **_kwargs):
        raise AssertionError("upload bytes must not be read before consent")

    monkeypatch.setattr(routes, "_ensure_web_consent", fake_ensure_web_consent)
    monkeypatch.setattr(routes, "read_limited_upload", fake_read_limited_upload)
    client = TestClient(create_app(settings=_settings(), session_factory=FakeSessionFactory()))

    response = client.post(
        "/check",
        data={
                        "language": "uz_latn",
            "text": "Bank xavfsizlik xizmatidanmiz. SMS kodni yuboring.",
        },
        files={"image": ("check.png", b"not-empty", "image/png")},
    )

    assert response.status_code == 400
    assert "result-block error" in response.text


def test_web_rejects_oversized_text_before_upload_or_engine(monkeypatch) -> None:
    async def fake_ensure_web_consent(*_args, **_kwargs) -> bool:
        return True

    async def fake_read_limited_upload(*_args, **_kwargs):
        raise AssertionError("oversized text must be rejected before reading upload")

    async def fake_run_check(*_args, **_kwargs):
        raise AssertionError("oversized text must not reach the engine")

    monkeypatch.setattr(routes, "_ensure_web_consent", fake_ensure_web_consent)
    monkeypatch.setattr(routes, "read_limited_upload", fake_read_limited_upload)
    monkeypatch.setattr(routes, "run_check", fake_run_check)
    client = TestClient(create_app(settings=_settings(), session_factory=FakeSessionFactory()))

    response = client.post(
        "/check",
        data={
                        "language": "uz_latn",
            "text": "x" * (routes.WEB_MAX_TEXT_CHARS + 1),
            "consent": "yes",
        },
    )

    assert response.status_code == 413
    assert "result-block error" in response.text


def test_web_ip_limit_survives_cookie_reset_and_spoofed_xff(monkeypatch) -> None:
    calls = []
    counts = {}

    async def fake_run_check(check_input, *args, **kwargs):
        calls.append((check_input, args, kwargs))
        return CheckResult(
            status=CheckStatus.ok,
            text="ok",
            language=check_input.language,
            input_type=check_input.input_type,
        )

    async def fake_ensure_web_consent(*_args, **_kwargs) -> bool:
        return True

    async def fake_increment_usage(
        _session, *, user_key: str, scope: str = "user", day=None
    ) -> int:
        _ = day
        key = (user_key, scope)
        counts[key] = counts.get(key, 0) + 1
        return counts[key]

    async def fake_refund_usage(_session, *, user_key: str, scope: str = "user", day=None) -> None:
        _ = day
        key = (user_key, scope)
        counts[key] = max(0, counts.get(key, 0) - 1)

    monkeypatch.setattr(routes, "run_check", fake_run_check)
    monkeypatch.setattr(routes, "_ensure_web_consent", fake_ensure_web_consent)
    monkeypatch.setattr(routes.repo, "increment_usage", fake_increment_usage)
    monkeypatch.setattr(routes.repo, "refund_usage", fake_refund_usage)

    app = create_app(
        settings=_settings(web_daily_limit=2),
        session_factory=FakeSessionFactory(),
    )
    payload = {
                "language": "uz_latn",
        "text": "Bank xavfsizlik xizmatidanmiz. SMS kodni yuboring.",
        "consent": "yes",
    }

    responses = [
        TestClient(app).post(
            "/check",
            data=payload,
            headers={"X-Forwarded-For": f"203.0.113.{index}"},
        )
        for index in range(7, 10)
    ]

    assert [response.status_code for response in responses] == [200, 200, 429]
    assert "Bugungi tekshiruvlar limiti tugadi" in responses[-1].text
    assert CheckStatus.rate_limited.value not in responses[-1].text
    assert len(calls) == 2
    assert len(counts) == 1
    ((user_key, scope), count) = next(iter(counts.items()))
    assert scope == "web_ip"
    assert "203.0.113" not in user_key
    assert count == 2
