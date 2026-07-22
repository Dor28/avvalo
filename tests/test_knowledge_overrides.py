"""Operator-authored knowledge cards layered onto the shipped YAML base.

Covers the privacy boundary (own declarative base), write validation, merge-by-ID
semantics, the fail-safe fallback, and the kb_version that must survive
``app.data.repo``'s write-time validation.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.data import repo as data_repo
from app.data.models import Base
from app.engine.knowledge import retrieve_knowledge
from app.engine.knowledge.loader import (
    FileKnowledgeStore,
    clear_active_knowledge_base,
    load_yaml_knowledge_base,
)
from app.engine.knowledge.types import KnowledgeLookupError
from app.engine.types import RuleHit
from app.knowledge_store import (
    KnowledgeCardDraft,
    KnowledgeStoreBase,
    create_card,
    derive_kb_version,
    load_overrides,
    merge_knowledge_base,
    refresh_knowledge_base,
    run_knowledge_refresh_job,
)


def _draft(**overrides) -> KnowledgeCardDraft:
    values = {
        "card_id": "family.test_card",
        "card_version": "1.0.0",
        "status": "approved",
        "reviewer": "unit-test",
        "mechanism": "The sender invents a new pressure story to rush a transfer.",
        "trigger_rule_ids": ["fs.urgency.deadline"],
        "trigger_signal_kinds": [],
        "retrieval_aliases": {"ru": ["выдуманная история"]},
        "red_flags": ["The story changes each time it is questioned."],
        "verify_steps": ["Confirm through a channel you found yourself."],
        "questions": ["Why can this not wait until tomorrow?"],
        "reviewed_case_ids": [],
    }
    return KnowledgeCardDraft(**{**values, **overrides})


@pytest_asyncio.fixture
async def knowledge_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(KnowledgeStoreBase.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture(autouse=True)
def _reset_active_bases():
    """The active base is process-level state; never leak it between tests."""

    clear_active_knowledge_base()
    yield
    clear_active_knowledge_base()


# --- privacy boundary -------------------------------------------------------


def test_cards_live_on_their_own_base_away_from_user_data() -> None:
    assert set(KnowledgeStoreBase.metadata.tables) == {"knowledge_card_override"}
    # The zero-content contract is enforced over Base only; keeping the card
    # table off it is what makes card text storable at all.
    assert "knowledge_card_override" not in Base.metadata.tables
    columns = KnowledgeStoreBase.metadata.tables["knowledge_card_override"].columns
    assert "user_key" not in columns


# --- write validation -------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"card_id": "NOT A CARD"},
        {"card_id": "nodots"},
        {"card_version": "not a version"},
        {"status": "published"},
        {"reviewer": ""},
        {"mechanism": ""},
        {"trigger_rule_ids": ["NOT A RULE"]},
        {"trigger_signal_kinds": ["Bad Kind"]},
        {"retrieval_aliases": {"en": ["hello"]}},
        {"retrieval_aliases": ["not-a-dict"]},
        {"red_flags": ["x" * 401]},
        {"questions": ["q"] * 13},
    ],
)
def test_invalid_drafts_are_rejected(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        _draft(**kwargs).normalized()


def test_valid_draft_projects_onto_the_engine_card_contract() -> None:
    card = _draft().as_card()
    assert card.id == "family.test_card"
    assert card.status == "approved"


# --- merge semantics --------------------------------------------------------


async def test_override_replaces_a_baseline_card_in_place(knowledge_session) -> None:
    base = load_yaml_knowledge_base()
    target = base.cards[0].id
    await create_card(knowledge_session, _draft(card_id=target, mechanism="Replaced mechanism."))
    await knowledge_session.commit()

    merged = merge_knowledge_base(base, await load_overrides(knowledge_session))

    assert len(merged.cards) == len(base.cards)
    assert [card.id for card in merged.cards] == [card.id for card in base.cards]
    assert next(c for c in merged.cards if c.id == target).mechanism == "Replaced mechanism."


async def test_override_with_a_new_id_is_appended(knowledge_session) -> None:
    base = load_yaml_knowledge_base()
    await create_card(knowledge_session, _draft(card_id="family.brand_new"))
    await knowledge_session.commit()

    merged = merge_knowledge_base(base, await load_overrides(knowledge_session))

    assert len(merged.cards) == len(base.cards) + 1
    assert merged.cards[-1].id == "family.brand_new"


@pytest.mark.parametrize("status", ["draft", "retired"])
async def test_non_approved_override_suppresses_the_baseline_card(
    knowledge_session, status: str
) -> None:
    base = load_yaml_knowledge_base()
    target = base.cards[0].id
    await create_card(knowledge_session, _draft(card_id=target, status=status))
    await knowledge_session.commit()

    merged = merge_knowledge_base(base, await load_overrides(knowledge_session))

    assert target not in {card.id for card in merged.cards}
    assert len(merged.cards) == len(base.cards) - 1


async def test_a_corrupt_row_is_skipped_rather_than_taking_the_base_down(
    knowledge_session,
) -> None:
    good = await create_card(knowledge_session, _draft(card_id="family.good_card"))
    bad = await create_card(knowledge_session, _draft(card_id="family.bad_card"))
    # Simulate a row written before a validation rule existed, or out of band.
    bad.retrieval_aliases = {"klingon": ["nuqneH"]}
    await knowledge_session.commit()

    overrides = await load_overrides(knowledge_session)

    assert [card.id for card in overrides.approved] == [good.card_id]


# --- kb_version -------------------------------------------------------------


def test_kb_version_is_unchanged_when_no_override_contributes() -> None:
    assert derive_kb_version("2026-07-15-v1", None) == "2026-07-15-v1"


def test_derived_kb_version_survives_the_event_write_validation() -> None:
    """``app.data.repo`` rejects a bad kb_version on every check_event write."""

    version = derive_kb_version("2026-07-15-v1", datetime(2026, 7, 22, 11, 30, tzinfo=UTC))

    assert version == "2026-07-15-v1.db20260722113000"
    # Assert against the real validator, not a copy of the regex.
    assert data_repo.VERSION_RE.fullmatch(version)


async def test_refresh_stamps_a_new_kb_version_when_an_override_exists(
    knowledge_session,
) -> None:
    baseline = load_yaml_knowledge_base().version
    await create_card(knowledge_session, _draft(card_id="family.version_probe"))
    await knowledge_session.commit()

    merged = await refresh_knowledge_base(knowledge_session)

    assert merged.version != baseline
    assert merged.version.startswith(baseline)
    assert data_repo.VERSION_RE.fullmatch(merged.version)


# --- fallback ---------------------------------------------------------------


def test_store_falls_back_to_yaml_before_any_refresh() -> None:
    assert FileKnowledgeStore().load() == load_yaml_knowledge_base()


async def test_refresh_job_never_raises_when_the_database_is_unreachable() -> None:
    class _BrokenFactory:
        def __call__(self):
            raise RuntimeError("database is down")

    await run_knowledge_refresh_job(_BrokenFactory())

    # The YAML baseline still answers checks — not an empty base.
    assert FileKnowledgeStore().load().cards


async def test_store_failure_degrades_to_unavailable_not_empty() -> None:
    """§5 requires degradation to be visible; an empty base would look healthy."""

    class _BrokenStore:
        def load(self):
            raise KnowledgeLookupError("knowledge files could not be loaded")

    result = await retrieve_knowledge(
        minimized_text="срочно пришлите код",
        rule_hits=[],
        signals=[],
        store=_BrokenStore(),
    )

    assert result.status == "unavailable"
    assert result.cards == ()


# --- end to end -------------------------------------------------------------


async def test_stored_card_reaches_retrieval_after_refresh(knowledge_session) -> None:
    await create_card(
        knowledge_session,
        _draft(card_id="family.e2e_card", trigger_rule_ids=["fs.urgency.deadline"]),
    )
    await knowledge_session.commit()
    await refresh_knowledge_base(knowledge_session)

    result = await retrieve_knowledge(
        minimized_text="срочно, только сегодня",
        rule_hits=[
            RuleHit(
                rule_id="fs.urgency.deadline",
                family="urgency_secrecy",
                message_key="urgency_deadline",
                severity=2,
            )
        ],
        signals=[],
    )

    assert "family.e2e_card" in result.knowledge_card_ids
    assert result.kb_version is not None
    assert data_repo.VERSION_RE.fullmatch(result.kb_version)


async def test_baseline_card_ids_are_unchanged_with_no_overrides(knowledge_session) -> None:
    baseline_ids = [card.id for card in load_yaml_knowledge_base().cards]

    merged = await refresh_knowledge_base(knowledge_session)

    assert [card.id for card in merged.cards] == baseline_ids
