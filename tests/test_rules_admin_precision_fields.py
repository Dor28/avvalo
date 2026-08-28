"""The operator editor can set the §6 precision controls.

Detection work is meant to live in ``rule_override`` rather than the public
repository, so a control an operator cannot reach from ``/admin/rules`` is a
control only an engineer can use. These tests pin the form path end to end:
saved through the browser form, merged into the active pack, and visible in the
matcher.
"""

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
from app.engine.rules.loader import clear_active_rule_pack
from app.rules_store import RuleStoreBase
from app.web.app import create_app

ADMIN_KEY = "test-admin-rule-key"


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        telegram_token="token",
        database_url="sqlite+aiosqlite:///:memory:",
        app_hmac_secret="test-hmac-secret",
        llm_base_url="http://localhost:11434/v1",
        llm_api_key="ollama",
        llm_model="qwen2.5:7b-instruct",
        web_session_secret="test-web-session-secret",
        admin_access_key=ADMIN_KEY,
    )


def _form(**overrides) -> dict:
    values = {
        "rule_id": "fs.test.precision",
        "family": "credential_theft",
        "description": "Added through the operator editor.",
        "message_key": "otp_request",
        "severity": "3",
        "emits_signal": "",
        "patterns_uz_latn": "kod",
        "patterns_uz_cyrl": "",
        "patterns_ru": "",
        "match_mode": "substring",
        "exclude_uz_latn": "",
        "exclude_uz_cyrl": "",
        "exclude_ru": "",
        "requires_any_of": "",
        "requires_all_of": "",
        "requires_signals": "",
        "sample": "",
        "override_id": "",
        "language": "ru",
    }
    return {**values, **overrides}


@pytest.fixture(autouse=True)
def _reset_active_packs():
    clear_active_rule_pack()
    yield
    clear_active_rule_pack()


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
    app = create_app(settings=_settings())
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    with TestClient(app) as test_client:
        yield test_client
    asyncio.run(engine.dispose())


def _login(client: TestClient) -> None:
    client.post("/admin/login", data={"access_key": ADMIN_KEY, "language": "ru"})


def _fired(text: str) -> set[str]:
    hits, _ = run_rules(text)
    return {hit.rule_id for hit in hits}


def test_the_form_exposes_every_precision_control(client: TestClient) -> None:
    _login(client)

    body = client.get("/admin/rules/new?language=ru").text

    assert 'name="match_mode"' in body
    assert 'name="exclude_uz_latn"' in body
    assert 'name="requires_any_of"' in body
    assert 'name="requires_signals"' in body


def test_saving_an_exclusion_suppresses_the_rule(client: TestClient) -> None:
    _login(client)

    response = client.post(
        "/admin/rules",
        data=_form(patterns_uz_latn="kodni yuboring", exclude_uz_latn="hech kimga aytmang"),
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "fs.test.precision" in _fired("kodni yuboring")
    assert "fs.test.precision" not in _fired("kodni yuboring, hech kimga aytmang")


def test_saving_word_prefix_mode_covers_uzbek_suffixes(client: TestClient) -> None:
    _login(client)

    client.post(
        "/admin/rules",
        data=_form(patterns_uz_latn="kod", match_mode="word_prefix"),
        follow_redirects=False,
    )

    assert "fs.test.precision" in _fired("kodni yuboring")
    assert "fs.test.precision" in _fired("kodingizni ayting")
    assert "fs.test.precision" not in _fired("bikod")


def test_saving_a_gate_keeps_the_rule_quiet_on_its_own(client: TestClient) -> None:
    _login(client)

    client.post(
        "/admin/rules",
        data=_form(
            patterns_uz_latn="oldindan",
            requires_any_of="fs.urgency.deadline",
        ),
        follow_redirects=False,
    )

    assert "fs.test.precision" not in _fired("oldindan to'lang")
    assert "fs.test.precision" in _fired("oldindan to'lang, faqat bugun")


def test_an_ordinary_save_stores_no_gate_and_no_exclusions(client: TestClient) -> None:
    """Empty form blocks must mean "absent", not an empty structure."""

    _login(client)

    response = client.post("/admin/rules", data=_form(), follow_redirects=False)

    assert response.status_code == 303
    assert "fs.test.precision" in _fired("kod")


def test_reopening_a_saved_rule_shows_its_controls(client: TestClient) -> None:
    """A round-trip through the form must not silently reset what was stored."""

    _login(client)
    client.post(
        "/admin/rules",
        data=_form(
            patterns_uz_latn="kod",
            match_mode="word_prefix",
            exclude_uz_latn="kodeks",
            requires_any_of="fs.urgency.deadline",
        ),
        follow_redirects=False,
    )

    listing = client.get("/admin/rules?language=ru").text
    # The override's own edit link, not "new" and not a baseline rule's.
    edit_url = next(
        url
        for url in re.findall(r'href="(/admin/rules/[^"]+)"', listing)
        if url.endswith("/edit?language=ru") and "/baseline/" not in url
    )
    body = client.get(edit_url).text

    assert "kodeks" in body
    assert "fs.urgency.deadline" in body
    assert 'value="word_prefix"' in body and "selected" in body


def test_editing_a_baseline_rule_preserves_its_precision_controls() -> None:
    """Opening a shipped rule in the editor must not drop fields it carries."""

    from app.engine.rules.loader import RuleDefinition, RuleRequirement
    from app.web.rules_admin import _draft_from_rule

    rule = RuleDefinition(
        id="fs.sample.rule",
        family="credential_theft",
        desc="sample",
        message_key="otp_request",
        severity=2,
        match={"uz_latn": ("kod",)},
        exclude={"uz_latn": ("kodeks",)},
        match_mode="word_prefix",
        requires=RuleRequirement(any_of=("fs.urgency.deadline",)),
    )

    draft = _draft_from_rule(rule)

    assert draft.match_mode == "word_prefix"
    assert draft.exclude["uz_latn"] == ["kodeks"]
    assert draft.requires == {"any_of": ["fs.urgency.deadline"]}
