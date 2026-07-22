"""Operator-authored rule overrides layered onto the shipped YAML pack.

Covers the privacy boundary (own declarative base), write validation, merge-by-ID
semantics, and the fail-safe fallback to the YAML baseline.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.data.models import Base
from app.engine.rules import run_rules
from app.engine.rules.loader import (
    RuleDefinition,
    clear_active_rule_pack,
    load_rule_pack,
    load_yaml_rule_pack,
)
from app.rules_store import (
    RuleOverrideDraft,
    RuleStoreBase,
    create_override,
    load_overrides,
    merge_rule_pack,
    refresh_rule_pack,
    run_rule_pack_refresh_job,
)


def _draft(**overrides) -> RuleOverrideDraft:
    values = {
        "rule_id": "fs.test.rule",
        "family": "credential_theft",
        "description": "Test rule used by the override suite.",
        "message_key": "otp_request",
        "severity": 3,
        "patterns": {"ru": ["кодовое слово банка"]},
    }
    return RuleOverrideDraft(**{**values, **overrides})


@pytest_asyncio.fixture
async def rules_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(RuleStoreBase.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture(autouse=True)
def _reset_active_packs():
    """The active pack is process-level state; never leak it between tests."""

    clear_active_rule_pack()
    yield
    clear_active_rule_pack()


# --- privacy boundary -------------------------------------------------------


def test_overrides_live_on_their_own_base_away_from_user_data() -> None:
    assert set(RuleStoreBase.metadata.tables) == {"rule_override"}
    # The zero-content contract is enforced over Base only; keeping the override
    # table off it is what makes patterns storable at all.
    assert "rule_override" not in Base.metadata.tables
    columns = RuleStoreBase.metadata.tables["rule_override"].columns
    assert "user_key" not in columns


# --- write validation -------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        {"rule_id": "NOT A RULE ID"},
        {"rule_id": "nodots"},
        {"family": "Bad Family"},
        {"message_key": "bad key"},
        {"severity": 0},
        {"severity": 9},
        {"description": ""},
        {"patterns": {"en": ["hello there"]}},
        {"patterns": {}},
        {"patterns": {"ru": ["ab"]}},  # too short to be a useful literal
        {"patterns": {"ru": ["regex:("]}},  # uncompilable
        {"patterns": {"ru": ["regex:"]}},  # empty expression
        {"emits_signal": "not a signal"},
    ],
)
def test_invalid_drafts_are_rejected(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        _draft(**kwargs).normalized()


def test_valid_regex_pattern_is_kept_with_its_prefix() -> None:
    normalized = _draft(patterns={"ru": [r"regex:код\s*\d{4,8}"]}).normalized()
    assert normalized.patterns["ru"] == [r"regex:код\s*\d{4,8}"]


def test_disabled_row_needs_no_patterns() -> None:
    normalized = _draft(disabled=True, patterns={"ru": []}).normalized()
    assert normalized.disabled is True


def test_rule_id_and_family_are_casefolded() -> None:
    normalized = _draft(rule_id="FS.Test.Rule", family="Credential_Theft").normalized()
    assert normalized.rule_id == "fs.test.rule"
    assert normalized.family == "credential_theft"


# --- merge semantics --------------------------------------------------------


def _definition(rule_id: str, *, patterns: dict[str, tuple[str, ...]]) -> RuleDefinition:
    return RuleDefinition(
        id=rule_id,
        family="credential_theft",
        desc="overridden",
        message_key="otp_request",
        severity=3,
        match=patterns,
    )


def test_override_replaces_a_baseline_rule_in_place() -> None:
    base = load_yaml_rule_pack()
    target = base.rules[0].id
    replacement = _definition(target, patterns={"ru": ("совершенно новый шаблон",)})

    merged = merge_rule_pack(base, (replacement,), frozenset())

    assert len(merged.rules) == len(base.rules)
    assert [rule.id for rule in merged.rules] == [rule.id for rule in base.rules]
    assert merged.descriptions[target] == "overridden"


def test_override_with_a_new_id_is_appended() -> None:
    base = load_yaml_rule_pack()
    addition = _definition("fs.brand.new", patterns={"ru": ("абсолютно новый шаблон",)})

    merged = merge_rule_pack(base, (addition,), frozenset())

    assert len(merged.rules) == len(base.rules) + 1
    assert merged.rules[-1].id == "fs.brand.new"


def test_disabled_id_suppresses_the_baseline_rule() -> None:
    base = load_yaml_rule_pack()
    target = base.rules[0].id

    merged = merge_rule_pack(base, (), frozenset({target}))

    assert target not in {rule.id for rule in merged.rules}
    assert target not in merged.descriptions
    assert len(merged.rules) == len(base.rules) - 1


def test_disabled_wins_over_an_addition_with_the_same_id() -> None:
    base = load_yaml_rule_pack()
    addition = _definition("fs.brand.new", patterns={"ru": ("абсолютно новый шаблон",)})

    merged = merge_rule_pack(base, (addition,), frozenset({"fs.brand.new"}))

    assert "fs.brand.new" not in {rule.id for rule in merged.rules}


# --- fallback ---------------------------------------------------------------


def test_load_rule_pack_falls_back_to_yaml_before_any_refresh() -> None:
    assert load_rule_pack() == load_yaml_rule_pack()


# --- end to end -------------------------------------------------------------


async def test_stored_override_fires_through_run_rules(rules_session) -> None:
    await create_override(
        rules_session,
        _draft(rule_id="fs.test.newpattern", patterns={"ru": ["секретная кодовая фраза"]}),
    )
    await rules_session.commit()

    await refresh_rule_pack(rules_session)
    hits, _signals = run_rules("Пришлите мне: секретная кодовая фраза")

    assert "fs.test.newpattern" in {hit.rule_id for hit in hits}


async def test_disabled_override_stops_a_baseline_rule_from_firing(rules_session) -> None:
    baseline_hits, _ = run_rules("Пришлите код из смс прямо сейчас")
    assert "fs.credential.otp" in {hit.rule_id for hit in baseline_hits}

    await create_override(
        rules_session,
        _draft(rule_id="fs.credential.otp", disabled=True, patterns={"ru": []}),
    )
    await rules_session.commit()

    await refresh_rule_pack(rules_session)
    hits, _ = run_rules("Пришлите код из смс прямо сейчас")

    assert "fs.credential.otp" not in {hit.rule_id for hit in hits}


async def test_a_corrupt_row_is_skipped_rather_than_taking_the_pack_down(
    rules_session,
) -> None:
    good = await create_override(rules_session, _draft(rule_id="fs.test.good"))
    bad = await create_override(rules_session, _draft(rule_id="fs.test.bad"))
    # Simulate a row written before a validation rule existed, or out of band.
    bad.patterns = {"ru": ["regex:("]}
    await rules_session.commit()

    definitions, disabled = await load_overrides(rules_session)

    assert [definition.id for definition in definitions] == [good.rule_id]
    assert disabled == frozenset()


async def test_refresh_job_never_raises_when_the_database_is_unreachable() -> None:
    class _BrokenFactory:
        def __call__(self):
            raise RuntimeError("database is down")

    await run_rule_pack_refresh_job(_BrokenFactory())

    # The YAML baseline still serves checks.
    assert load_rule_pack().rules
