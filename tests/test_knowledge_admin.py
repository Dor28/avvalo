"""Operator-only card editor: auth gating, retrieval dry-run, immediate republish."""

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
from app.engine.knowledge import retrieve_knowledge
from app.engine.knowledge.loader import clear_active_knowledge_base
from app.engine.types import RuleHit
from app.knowledge_store import KnowledgeStoreBase
from app.rules_store import RuleStoreBase
from app.web.app import create_app
from app.web.knowledge_copy import KNOWLEDGE_COPY

ADMIN_KEY = "test-admin-card-key"
SAMPLE = "Срочно, только сегодня — переведите деньги"
URGENCY_HIT = RuleHit(
    rule_id="fs.urgency.deadline",
    family="urgency_secrecy",
    message_key="urgency_deadline",
    severity=2,
)


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
        "card_id": "family.admin_card",
        "card_version": "1.0.0",
        "status": "approved",
        "reviewer": "founder",
        "mechanism": "The sender manufactures a deadline to prevent independent checking.",
        "trigger_rule_ids": "fs.urgency.deadline",
        "trigger_signal_kinds": "",
        "red_flags": "The deadline moves when questioned.",
        "verify_steps": "Confirm through a channel you found yourself.",
        "questions": "Why can this not wait until tomorrow?",
        "reviewed_case_ids": "",
        "aliases_uz_latn": "",
        "aliases_uz_cyrl": "",
        "aliases_ru": "",
        "sample": "",
        "override_id": "",
        "language": "ru",
    }
    return {**values, **overrides}


@pytest.fixture(autouse=True)
def _reset_active_bases():
    clear_active_knowledge_base()
    yield
    clear_active_knowledge_base()


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
            await connection.run_sync(KnowledgeStoreBase.metadata.create_all)
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


async def _retrieved_ids() -> list[str]:
    result = await retrieve_knowledge(
        minimized_text=SAMPLE,
        rule_hits=[URGENCY_HIT],
        signals=[],
    )
    return result.knowledge_card_ids


# --- access control ---------------------------------------------------------


def test_card_routes_redirect_to_login_when_signed_out(client) -> None:
    response = client.get("/admin/cards", follow_redirects=False)
    assert response.status_code == 303
    assert "/admin/login" in response.headers["location"]


def test_card_routes_are_absent_without_a_configured_admin_key() -> None:
    app = create_app(settings=_settings(admin_access_key=None))
    with TestClient(app) as anonymous:
        assert anonymous.get("/admin/cards").status_code == 404


def test_saving_requires_a_same_origin_request(client) -> None:
    _login(client)
    response = client.post(
        "/admin/cards",
        data=_form(),
        headers={"origin": "https://attacker.example"},
        follow_redirects=False,
    )
    assert response.status_code >= 400


def test_all_three_admin_sections_are_reachable_from_the_shared_header(client) -> None:
    """Jinja renders an undefined name as an empty string, so assert the labels."""

    _login(client)
    for path in ("/admin/posts", "/admin/rules", "/admin/cards"):
        body = client.get(f"{path}?language=ru").text
        assert 'href="/admin/posts?language=ru"' in body, path
        assert 'href="/admin/rules?language=ru"' in body, path
        assert 'href="/admin/cards?language=ru"' in body, path
        assert "Карточки знаний" in body, path


def test_every_copy_key_exists_in_both_reply_languages() -> None:
    """Cyrillic-Uzbek is retired as a reply language; aliases still keep it."""

    reference = KNOWLEDGE_COPY["ru"]
    for language in ("uz_latn", "ru"):
        assert set(KNOWLEDGE_COPY[language]) == set(reference), language
        assert set(KNOWLEDGE_COPY[language]["errors"]) == set(reference["errors"]), language


# --- dry run ----------------------------------------------------------------


def test_preview_reports_selection_without_saving(client) -> None:
    _login(client)
    response = client.post("/admin/cards/preview", data=_form(sample=SAMPLE))

    assert response.status_code == 200
    assert "Карточка выбрана" in response.text
    # Nothing was persisted, so the list stays empty.
    assert "family.admin_card" not in client.get("/admin/cards").text


def test_preview_reports_non_selection_for_text_the_card_cannot_match(client) -> None:
    _login(client)
    response = client.post(
        "/admin/cards/preview",
        data=_form(trigger_rule_ids="", sample="Здравствуйте, во сколько встреча?"),
    )

    assert response.status_code == 200
    assert "Карточка не выбрана" in response.text


def test_non_selection_and_not_approved_are_different_messages(client) -> None:
    """Collapsing these would leave the operator unable to tell why a card is silent."""

    _login(client)
    not_selected = client.post(
        "/admin/cards/preview",
        data=_form(trigger_rule_ids="", sample="Здравствуйте, во сколько встреча?"),
    ).text
    not_approved = client.post(
        "/admin/cards/preview", data=_form(status="draft", sample=SAMPLE)
    ).text

    assert KNOWLEDGE_COPY["ru"]["preview_not_selected"] in not_selected
    assert "не `approved`" in not_approved
    assert KNOWLEDGE_COPY["ru"]["preview_not_selected"] not in not_approved


def test_preview_surfaces_an_invalid_draft_instead_of_saving_it(client) -> None:
    _login(client)
    response = client.post(
        "/admin/cards/preview", data=_form(card_id="NOT A CARD", sample=SAMPLE)
    )

    assert response.status_code == 200
    assert "ID карточки" in response.text


# --- persistence and republish ---------------------------------------------


def test_saving_a_card_republishes_the_base_immediately(client) -> None:
    _login(client)
    assert "family.admin_card" not in asyncio.run(_retrieved_ids())

    response = client.post("/admin/cards", data=_form(), follow_redirects=False)
    assert response.status_code == 303

    # No waiting for the refresh interval: the edit is in force now.
    assert "family.admin_card" in asyncio.run(_retrieved_ids())
    assert "family.admin_card" in client.get("/admin/cards").text


def test_an_invalid_draft_is_rejected_with_a_localized_message(client) -> None:
    _login(client)
    response = client.post("/admin/cards", data=_form(card_id="NOT A CARD"))

    assert response.status_code == 400
    assert "ID карточки" in response.text
    assert "NOT A CARD" not in client.get("/admin/cards").text


def test_a_duplicate_card_id_is_reported_rather_than_crashing(client) -> None:
    _login(client)
    assert client.post("/admin/cards", data=_form(), follow_redirects=False).status_code == 303

    response = client.post("/admin/cards", data=_form())

    assert response.status_code == 400
    assert "уже существует" in response.text


def test_deleting_an_override_restores_the_baseline_card(client) -> None:
    _login(client)
    client.post(
        "/admin/cards",
        data=_form(card_id="family.urgency_secrecy", status="retired"),
        follow_redirects=False,
    )
    assert "family.urgency_secrecy" not in asyncio.run(_retrieved_ids())

    listing = client.get("/admin/cards").text
    match = re.search(r"/admin/cards/([0-9a-f-]{36})/edit", listing)
    assert match is not None, "the listing must link to the override's editor"
    response = client.post(
        f"/admin/cards/{match.group(1)}/delete",
        data={"language": "ru"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert "family.urgency_secrecy" in asyncio.run(_retrieved_ids())
