"""Operator-only rule editor: auth gating, dry-run, and immediate republish."""

from __future__ import annotations

import asyncio
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.content import EditorialBase
from app.data.models import Base
from app.engine.rules import run_rules
from app.engine.rules.loader import clear_active_rule_packs
from app.rules_store import RuleStoreBase
from app.web.app import create_app

ADMIN_KEY = "test-admin-rule-key"
SAMPLE = "Пришлите мне секретную кодовую фразу прямо сейчас"


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


def _form(**overrides) -> dict:
    values = {
        "rule_id": "fs.test.adminrule",
        "family": "credential_theft",
        "description": "Added through the operator editor.",
        "message_key": "otp_request",
        "severity": "3",
        "emits_signal": "",
        "patterns_uz_latn": "",
        "patterns_uz_cyrl": "",
        "patterns_ru": "секретную кодовую фразу",
        "sample": "",
        "override_id": "",
        "language": "ru",
    }
    return {**values, **overrides}


@pytest.fixture(autouse=True)
def _reset_active_packs():
    clear_active_rule_packs()
    yield
    clear_active_rule_packs()


@pytest.fixture
def client():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async def _create() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await connection.run_sync(RuleStoreBase.metadata.create_all)
            await connection.run_sync(EditorialBase.metadata.create_all)

    asyncio.run(_create())
    factory = async_sessionmaker(engine, expire_on_commit=False)
    app = create_app(settings=_settings())
    app.state.session_factory = factory
    with TestClient(app) as test_client:
        yield test_client
    asyncio.run(engine.dispose())


def _login(client: TestClient) -> None:
    response = client.post(
        "/admin/login", data={"access_key": ADMIN_KEY, "language": "ru"}, follow_redirects=False
    )
    assert response.status_code == 303


# --- access control ---------------------------------------------------------


def test_rule_routes_redirect_to_login_when_signed_out(client) -> None:
    response = client.get("/admin/rules", follow_redirects=False)
    assert response.status_code == 303
    assert "/admin/login" in response.headers["location"]


def test_rule_routes_are_absent_without_a_configured_admin_key() -> None:
    app = create_app(settings=_settings(admin_access_key=None))
    with TestClient(app) as anonymous:
        assert anonymous.get("/admin/rules").status_code == 404


def test_saving_requires_a_same_origin_request(client) -> None:
    _login(client)
    response = client.post(
        "/admin/rules",
        data=_form(),
        headers={"origin": "https://attacker.example"},
        follow_redirects=False,
    )
    assert response.status_code >= 400


def test_both_admin_sections_are_reachable_from_the_shared_header(client) -> None:
    """Jinja renders an undefined name as an empty string, so assert the label."""

    _login(client)
    for path in ("/admin/posts", "/admin/rules"):
        body = client.get(f"{path}?language=ru").text
        assert 'href="/admin/rules?language=ru"' in body, path
        assert 'href="/admin/posts?language=ru"' in body, path
        assert "Шаблоны правил" in body, path


# --- dry run ----------------------------------------------------------------


def test_preview_reports_a_matching_pattern_without_saving(client) -> None:
    _login(client)
    response = client.post("/admin/rules/preview", data=_form(sample=SAMPLE))

    assert response.status_code == 200
    assert "секретную кодовую фразу" in response.text
    # Nothing was persisted, so the list stays empty.
    assert "fs.test.adminrule" not in client.get("/admin/rules").text


def test_preview_reports_a_non_matching_pattern(client) -> None:
    _login(client)
    response = client.post(
        "/admin/rules/preview", data=_form(sample="Здравствуйте, во сколько встреча?")
    )

    assert response.status_code == 200
    assert "не сработало" in response.text


def test_preview_surfaces_an_uncompilable_regex_instead_of_saving_it(client) -> None:
    _login(client)
    response = client.post(
        "/admin/rules/preview", data=_form(patterns_ru="regex:(", sample=SAMPLE)
    )

    assert response.status_code == 200
    assert "regex" in response.text.lower()


# --- persistence and republish ---------------------------------------------


def test_saving_an_override_republishes_the_pack_immediately(client) -> None:
    _login(client)
    baseline, _ = run_rules(SAMPLE, "family")
    assert "fs.test.adminrule" not in {hit.rule_id for hit in baseline}

    response = client.post("/admin/rules", data=_form(), follow_redirects=False)
    assert response.status_code == 303

    # No waiting for the refresh interval: the edit is in force now.
    hits, _ = run_rules(SAMPLE, "family")
    assert "fs.test.adminrule" in {hit.rule_id for hit in hits}
    assert "fs.test.adminrule" in client.get("/admin/rules").text


def test_an_invalid_draft_is_rejected_with_a_localized_message(client) -> None:
    _login(client)
    response = client.post("/admin/rules", data=_form(rule_id="NOT VALID"))

    assert response.status_code == 400
    assert "ID правила" in response.text
    assert "NOT VALID" not in client.get("/admin/rules").text


def test_a_duplicate_rule_id_is_reported_rather_than_crashing(client) -> None:
    _login(client)
    assert client.post("/admin/rules", data=_form(), follow_redirects=False).status_code == 303

    response = client.post("/admin/rules", data=_form())

    assert response.status_code == 400
    assert "уже существует" in response.text


def test_deleting_an_override_restores_the_baseline_rule(client) -> None:
    _login(client)
    client.post(
        "/admin/rules",
        data=_form(rule_id="fs.credential.otp", disabled="true", patterns_ru=""),
        follow_redirects=False,
    )
    hits, _ = run_rules("Пришлите код из смс", "family")
    assert "fs.credential.otp" not in {hit.rule_id for hit in hits}

    listing = client.get("/admin/rules").text
    match = re.search(r"/admin/rules/([0-9a-f-]{36})/edit", listing)
    assert match is not None, "the listing must link to the override's editor"
    override_id = match.group(1)
    response = client.post(
        f"/admin/rules/{override_id}/delete", data={"language": "ru"}, follow_redirects=False
    )

    assert response.status_code == 303
    restored, _ = run_rules("Пришлите код из смс", "family")
    assert "fs.credential.otp" in {hit.rule_id for hit in restored}
