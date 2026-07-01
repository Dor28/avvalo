"""T13 - web channel parity and abuse gates."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.engine import CheckResult, CheckStatus, InputType, Language
from app.web import routes
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
    assert "/family-shield" in paths
    assert "/seller-guard" in paths
    assert "/check" in paths
    assert "/privacy" in paths
    assert "/healthz" in paths


def test_product_pages_are_separate_and_localized() -> None:
    client = TestClient(create_app(settings=_settings()))

    family = client.get("/family-shield?language=uz_latn")
    seller = client.get("/seller-guard?language=ru")
    seller_title_ru = (
        "\u0417\u0430\u0449\u0438\u0442\u0430 \u043f\u0440\u043e\u0434\u0430\u0432\u0446\u0430"
    )

    assert family.status_code == 200
    assert seller.status_code == 200
    assert 'value="family_shield"' in family.text
    assert 'value="seller_guard"' in seller.text
    assert "/seller-guard?language=uz_latn" in family.text
    assert "/family-shield?language=ru" in seller.text
    assert 'type="radio"' not in family.text
    assert 'type="radio"' not in seller.text
    assert seller_title_ru in seller.text


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
            "face": "family_shield",
            "language": "uz_latn",
            "text": "Bank xavfsizlik xizmatidanmiz. SMS kodni yuboring.",
            "consent": "yes",
        },
    )

    assert response.status_code == 200
    assert "checked by shared engine" in response.text
    assert len(calls) == 1
    check_input, _args, kwargs = calls[0]
    assert check_input.input_type is InputType.text
    assert check_input.language is Language.uz_latn
    assert check_input.raw_text.startswith("Bank xavfsizlik")
    assert kwargs["rate_limit_override"] == 5
    assert kwargs["session"].__class__ is FakeSession


def test_web_check_fails_closed_without_session_factory(monkeypatch) -> None:
    async def fake_run_check(*_args, **_kwargs):
        raise AssertionError("miswired web app must not process checks")

    monkeypatch.setattr(routes, "run_check", fake_run_check)
    client = TestClient(create_app(settings=_settings()))

    response = client.post(
        "/check",
        data={
            "face": "family_shield",
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
            "face": "family_shield",
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
            "face": "family_shield",
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
            "face": "family_shield",
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

    async def fake_increment_usage(_session, *, user_key: str, face: str, day=None) -> int:
        _ = day
        key = (user_key, face)
        counts[key] = counts.get(key, 0) + 1
        return counts[key]

    async def fake_refund_usage(_session, *, user_key: str, face: str, day=None) -> None:
        _ = day
        key = (user_key, face)
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
        "face": "family_shield",
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
    assert CheckStatus.rate_limited.value in responses[-1].text
    assert len(calls) == 2
    assert len(counts) == 1
    ((user_key, face), count) = next(iter(counts.items()))
    assert face == "web_ip:family_shield"
    assert "203.0.113" not in user_key
    assert count == 2
