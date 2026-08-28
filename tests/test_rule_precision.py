"""Rule-layer precision controls: exclude, match_mode, and requires.

PIPELINE_V2 §6. All three fields are optional and every rule written before they
existed must keep matching exactly as it did, so the backward-compatibility
section is as load-bearing as the feature sections. The dry-run parity test is
what keeps the operator preview at ``/admin/rules`` from disagreeing with what
production matching does.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.engine.rules import loader as rules_loader
from app.engine.rules import matching_patterns, run_rules
from app.engine.rules.loader import (
    MATCH_MODE_SUBSTRING,
    MATCH_MODE_WORD_PREFIX,
    RuleDefinition,
    RulePack,
    RuleRequirement,
    clear_active_rule_pack,
    load_rule_pack,
    load_yaml_rule_pack,
    set_active_rule_pack,
)
from app.rules_store import (
    RuleOverrideDraft,
    RuleStoreBase,
    create_override,
    load_overrides,
    merge_rule_pack,
    preview_rule,
    refresh_rule_pack,
    run_rule_pack_refresh_job,
)

CARD_TEXT = "karta 8600 1234 1234 5678"


@pytest.fixture(autouse=True)
def _reset_pack_state() -> Iterator[None]:
    """Both packs are process-level state; never leak them between tests."""

    clear_active_rule_pack()
    load_yaml_rule_pack.cache_clear()
    yield
    clear_active_rule_pack()
    load_yaml_rule_pack.cache_clear()


@pytest_asyncio.fixture
async def rules_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(RuleStoreBase.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def _rule(rule_id: str, **overrides) -> RuleDefinition:
    values = {
        "id": rule_id,
        "family": "credential_theft",
        "desc": f"Test rule {rule_id}.",
        "message_key": "otp_request",
        "severity": 2,
        "match": {"uz_latn": ("kod",)},
    }
    return RuleDefinition(**{**values, **overrides})


def _activate(*rules: RuleDefinition) -> RulePack:
    pack = RulePack(rules=rules, descriptions={rule.id: rule.desc for rule in rules})
    set_active_rule_pack(pack)
    return pack


def _fired(text: str) -> set[str]:
    hits, _signals = run_rules(text)
    return {hit.rule_id for hit in hits}


def _draft(**overrides) -> RuleOverrideDraft:
    values = {
        "rule_id": "fs.test.precision",
        "family": "credential_theft",
        "description": "Test rule used by the precision suite.",
        "message_key": "otp_request",
        "severity": 3,
        "patterns": {"uz_latn": ["kod"]},
    }
    return RuleOverrideDraft(**{**values, **overrides})


def _write_pack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, document: str) -> None:
    """Point the YAML loader at a one-file pack written for this test."""

    (tmp_path / "pack.yaml").write_text(document, encoding="utf-8")
    monkeypatch.setattr(rules_loader, "RULE_PACK_DIR", tmp_path)
    load_yaml_rule_pack.cache_clear()


# --- exclude ----------------------------------------------------------------


def test_exclude_suppresses_a_rule_that_would_otherwise_fire() -> None:
    _activate(_rule("fs.test.excluded", exclude={"uz_latn": ("promo kod",)}))

    assert _fired("kodni yuboring") == {"fs.test.excluded"}
    assert _fired("promo kod bering, kodni yuboring") == set()


def test_exclude_wins_across_language_groups() -> None:
    """An exclusion is not scoped to the group whose keyword matched."""

    _activate(
        _rule(
            "fs.test.crossscript",
            match={"ru": ("код",), "uz_latn": ("kod",)},
            exclude={"ru": ("промокод магазина",)},
        )
    )

    assert _fired("kodni yuboring") == {"fs.test.crossscript"}
    assert _fired("kodni yuboring, промокод магазина") == set()


def test_a_rule_without_exclude_is_never_suppressed() -> None:
    _activate(_rule("fs.test.plain"))

    assert _fired("promo kod bering, kodni yuboring") == {"fs.test.plain"}


# --- match_mode -------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["kodni yuboring", "kodingizni ayting", "kodini kiriting", "sms kod keldi"],
)
def test_word_prefix_matches_inflected_uzbek_forms(text: str) -> None:
    _activate(_rule("fs.test.wordprefix", match_mode=MATCH_MODE_WORD_PREFIX))

    assert _fired(text) == {"fs.test.wordprefix"}


def test_word_prefix_does_not_match_inside_a_word() -> None:
    _activate(_rule("fs.test.wordprefix", match_mode=MATCH_MODE_WORD_PREFIX))

    assert _fired("bikod nima degani") == set()


def test_substring_mode_still_matches_inside_a_word() -> None:
    """The default mode is unchanged: it is what every existing rule uses."""

    _activate(_rule("fs.test.substring"))

    assert _rule("fs.test.substring").match_mode == MATCH_MODE_SUBSTRING
    assert _fired("bikod nima degani") == {"fs.test.substring"}


def test_exclude_and_word_prefix_compose_to_reject_kodeks() -> None:
    """`word_prefix` still matches "kodeks"; the exclusion is what stops it."""

    _activate(
        _rule(
            "fs.test.composed",
            match_mode=MATCH_MODE_WORD_PREFIX,
            exclude={"uz_latn": ("kodeks",)},
        )
    )

    assert _fired("kodingizni yuboring") == {"fs.test.composed"}
    assert _fired("jinoyat kodeksi 100-modda") == set()
    assert _fired("bikod") == set()


@pytest.mark.parametrize("mode", [MATCH_MODE_SUBSTRING, MATCH_MODE_WORD_PREFIX])
def test_regex_patterns_keep_working_under_both_match_modes(mode: str) -> None:
    _activate(
        _rule(
            "fs.test.regex",
            match={"uz_latn": (r"regex:kod\s*\d{4,8}",)},
            match_mode=mode,
        )
    )

    assert _fired("bizning kod 123456 keldi") == {"fs.test.regex"}
    assert _fired("bizning kod keldi") == set()


def test_an_uncompilable_regex_still_degrades_to_no_match() -> None:
    _activate(_rule("fs.test.badregex", match={"uz_latn": ("regex:(",)}))

    assert _fired("kodni yuboring") == set()


# --- requires ---------------------------------------------------------------


def test_requires_any_of_gates_a_rule_both_ways() -> None:
    _activate(
        _rule("fs.test.urgency", match={"uz_latn": ("shoshiling",)}),
        _rule(
            "fs.test.gated",
            match={"uz_latn": ("oldindan to'lov",)},
            requires=RuleRequirement(any_of=("fs.test.urgency",)),
        ),
    )

    assert _fired("oldindan to'lov kerak") == set()
    assert _fired("shoshiling, oldindan to'lov kerak") == {
        "fs.test.urgency",
        "fs.test.gated",
    }


def test_requires_all_of_needs_every_referenced_rule() -> None:
    _activate(
        _rule("fs.test.urgency", match={"uz_latn": ("shoshiling",)}),
        _rule("fs.test.authority", match={"uz_latn": ("bank xodimi",)}),
        _rule(
            "fs.test.gated",
            match={"uz_latn": ("oldindan to'lov",)},
            requires=RuleRequirement(all_of=("fs.test.urgency", "fs.test.authority")),
        ),
    )

    assert "fs.test.gated" not in _fired("shoshiling, oldindan to'lov kerak")
    assert "fs.test.gated" in _fired("bank xodimi: shoshiling, oldindan to'lov kerak")


def test_requires_signals_gates_on_a_structural_signal() -> None:
    _activate(
        _rule(
            "fs.test.gated",
            match={"uz_latn": ("oldindan to'lov",)},
            requires=RuleRequirement(signals=("card",)),
        )
    )

    assert _fired("oldindan to'lov kerak") == set()
    assert _fired(f"oldindan to'lov kerak, {CARD_TEXT}") == {"fs.test.gated"}


def test_a_gated_rule_still_emits_its_own_signal() -> None:
    _activate(
        _rule("fs.test.urgency", match={"uz_latn": ("shoshiling",)}),
        _rule(
            "fs.test.gated",
            match={"uz_latn": ("oldindan to'lov",)},
            emits_signal="card_personal",
            requires=RuleRequirement(any_of=("fs.test.urgency",)),
        ),
    )

    _hits, signals = run_rules("shoshiling, oldindan to'lov kerak")

    assert "card_personal" in {signal.kind for signal in signals}


def test_a_gated_rules_signal_does_not_feed_another_gate() -> None:
    """One pass, no fixpoint: the gate sees the base result only."""

    _activate(
        _rule("fs.test.urgency", match={"uz_latn": ("shoshiling",)}),
        _rule(
            "fs.test.emitter",
            match={"uz_latn": ("oldindan to'lov",)},
            emits_signal="card_personal",
            requires=RuleRequirement(any_of=("fs.test.urgency",)),
        ),
        _rule(
            "fs.test.consumer",
            match={"uz_latn": ("kartaga tashlang",)},
            requires=RuleRequirement(signals=("card_personal",)),
        ),
    )

    fired = _fired("shoshiling, oldindan to'lov kerak, kartaga tashlang")

    assert "fs.test.emitter" in fired
    assert "fs.test.consumer" not in fired


def test_a_gate_referencing_an_unknown_rule_is_simply_never_satisfied() -> None:
    """A dangling reference must not fail the pack — disabling a rule creates one."""

    _activate(
        _rule(
            "fs.test.gated",
            requires=RuleRequirement(any_of=("fs.test.does_not_exist",)),
        )
    )

    assert _fired("kodni yuboring") == set()


def test_exclude_still_applies_to_a_rule_whose_gate_is_open() -> None:
    _activate(
        _rule("fs.test.urgency", match={"uz_latn": ("shoshiling",)}),
        _rule(
            "fs.test.gated",
            exclude={"uz_latn": ("promo kod",)},
            requires=RuleRequirement(any_of=("fs.test.urgency",)),
        ),
    )

    assert _fired("shoshiling, kodni yuboring") == {"fs.test.urgency", "fs.test.gated"}
    assert _fired("shoshiling, promo kod, kodni yuboring") == {"fs.test.urgency"}


# --- the load-time constraint -----------------------------------------------


def test_a_pack_gating_a_rule_on_another_gated_rule_fails_to_load() -> None:
    first = _rule("fs.test.first", requires=RuleRequirement(signals=("card",)))
    second = _rule("fs.test.second", requires=RuleRequirement(any_of=("fs.test.first",)))

    with pytest.raises(ValueError, match=re.escape("fs.test.first")):
        RulePack(rules=(first, second), descriptions={})


def test_a_rule_may_not_gate_itself() -> None:
    rule = _rule("fs.test.self", requires=RuleRequirement(all_of=("fs.test.self",)))

    with pytest.raises(ValueError, match=re.escape("fs.test.self")):
        RulePack(rules=(rule,), descriptions={})


def test_a_yaml_pack_violating_the_constraint_raises_on_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_pack(
        tmp_path,
        monkeypatch,
        """
families:
  - family: credential_theft
    rules:
      - id: fs.test.first
        desc: "First gated rule."
        message_key: otp_request
        severity: 2
        requires:
          signals: [card]
        match:
          uz_latn: ["kod"]
      - id: fs.test.second
        desc: "Gated on a gated rule."
        message_key: otp_request
        severity: 2
        requires:
          any_of: [fs.test.first]
        match:
          uz_latn: ["parol"]
""",
    )

    with pytest.raises(ValueError, match=re.escape("fs.test.first")):
        load_yaml_rule_pack()


def test_a_violating_override_leaves_the_shipped_baseline_serving(rules_factory) -> None:
    """The merge fails, so the pack in force is untouched — never an empty pack."""

    base = load_yaml_rule_pack()
    first = _rule("fs.test.first", requires=RuleRequirement(signals=("card",)))
    second = _rule("fs.test.second", requires=RuleRequirement(any_of=("fs.test.first",)))

    with pytest.raises(ValueError):
        merge_rule_pack(base, (first, second), frozenset())

    assert load_rule_pack() == base


async def test_the_refresh_job_swallows_a_violating_merge(rules_factory) -> None:
    async with rules_factory() as session:
        await create_override(
            session,
            _draft(
                rule_id="fs.test.first",
                patterns={"uz_latn": ["kod"]},
                requires={"signals": ["card"]},
            ),
        )
        await create_override(
            session,
            _draft(
                rule_id="fs.test.second",
                patterns={"uz_latn": ["parol"]},
                requires={"any_of": ["fs.test.first"]},
            ),
        )
        await session.commit()

    await run_rule_pack_refresh_job(rules_factory)

    # The shipped YAML baseline still serves checks, with neither bad rule in it.
    assert load_rule_pack() == load_yaml_rule_pack()
    assert "fs.test.second" not in {rule.id for rule in load_rule_pack().rules}
    assert load_rule_pack().rules


# --- YAML parsing -----------------------------------------------------------


def test_yaml_rules_carry_the_parsed_precision_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_pack(
        tmp_path,
        monkeypatch,
        """
families:
  - family: upfront_payment
    rules:
      - id: fs.test.base
        desc: "Ungated base rule."
        message_key: urgency_deadline
        severity: 2
        match:
          uz_latn: ["shoshiling"]
      - id: fs.test.tuned
        desc: "Gated, word-prefixed, with an exclusion."
        message_key: upfront_payment
        severity: 2
        match_mode: word_prefix
        exclude:
          uz_latn: ["kodeks"]
        requires:
          any_of: [fs.test.base]
          signals: [card]
        match:
          uz_latn: ["kod"]
""",
    )

    pack = load_yaml_rule_pack()
    tuned = next(rule for rule in pack.rules if rule.id == "fs.test.tuned")
    base = next(rule for rule in pack.rules if rule.id == "fs.test.base")

    assert tuned.match_mode == MATCH_MODE_WORD_PREFIX
    assert tuned.exclude == {"uz_latn": ("kodeks",)}
    assert tuned.requires == RuleRequirement(any_of=("fs.test.base",), signals=("card",))
    assert base.match_mode == MATCH_MODE_SUBSTRING
    assert base.exclude == {} and base.requires is None


@pytest.mark.parametrize(
    "block",
    [
        "        match_mode: prefix\n",
        "        exclude: []\n",
        "        exclude: {}\n",
        "        requires: []\n",
        "        requires:\n          maybe_of: [fs.test.base]\n",
        "        requires:\n          any_of: []\n",
        "        requires:\n          any_of: [3]\n",
    ],
)
def test_a_malformed_precision_block_fails_the_pack(
    block: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_pack(
        tmp_path,
        monkeypatch,
        f"""
families:
  - family: credential_theft
    rules:
      - id: fs.test.bad
        desc: "Rule with a malformed precision block."
        message_key: otp_request
        severity: 2
{block}        match:
          uz_latn: ["kod"]
""",
    )

    with pytest.raises(ValueError):
        load_yaml_rule_pack()


# --- the operator dry-run ---------------------------------------------------


def test_the_dry_run_reports_nothing_for_an_excluded_sample() -> None:
    rule = _rule("fs.test.excluded", exclude={"uz_latn": ("promo kod",)})

    assert matching_patterns(rule, "kodni yuboring") == ("kod",)
    assert matching_patterns(rule, "promo kod, kodni yuboring") == ()


def test_the_dry_run_reflects_an_unmet_requires_gate() -> None:
    _activate(_rule("fs.test.urgency", match={"uz_latn": ("shoshiling",)}))
    gated = _rule("fs.test.gated", requires=RuleRequirement(any_of=("fs.test.urgency",)))

    assert matching_patterns(gated, "kodni yuboring") == ()
    assert matching_patterns(gated, "shoshiling, kodni yuboring") == ("kod",)


def test_the_dry_run_agrees_with_production_on_every_sample() -> None:
    rules = (
        _rule("fs.test.urgency", match={"uz_latn": ("shoshiling",)}),
        _rule(
            "fs.test.gated",
            match_mode=MATCH_MODE_WORD_PREFIX,
            exclude={"uz_latn": ("kodeks",)},
            requires=RuleRequirement(any_of=("fs.test.urgency",), signals=("card",)),
        ),
    )
    _activate(*rules)
    samples = [
        "kodni yuboring",
        "shoshiling, kodni yuboring",
        f"shoshiling, kodni yuboring, {CARD_TEXT}",
        f"shoshiling, jinoyat kodeksi, {CARD_TEXT}",
        f"shoshiling, bikod, {CARD_TEXT}",
        "salom, ertaga uchrashamizmi",
    ]

    for sample in samples:
        fired = _fired(sample)
        for rule in rules:
            assert bool(matching_patterns(rule, sample)) is (rule.id in fired), (
                f"{rule.id} disagrees on {sample!r}"
            )


def test_a_previewed_gate_is_not_satisfied_by_the_stored_version_of_itself() -> None:
    _activate(_rule("fs.test.gated", match={"uz_latn": ("kod",)}))
    edited = _rule("fs.test.gated", requires=RuleRequirement(any_of=("fs.test.gated",)))

    assert matching_patterns(edited, "kodni yuboring") == ()


async def test_preview_rule_carries_the_draft_precision_fields() -> None:
    draft = _draft(
        exclude={"uz_latn": ["kodeks"]},
        match_mode=MATCH_MODE_WORD_PREFIX,
    )

    assert preview_rule(draft, "kodingizni yuboring") == ("kod",)
    assert preview_rule(draft, "jinoyat kodeksi") == ()
    assert preview_rule(draft, "bikod") == ()


# --- the override store -----------------------------------------------------


def test_a_draft_normalizes_the_new_fields() -> None:
    normalized = _draft(
        exclude={"uz_latn": ["  kodeks  "]},
        match_mode="WORD_PREFIX",
        requires={"any_of": ["FS.Test.Base"], "signals": ["card"]},
    ).normalized()

    assert normalized.exclude == {"uz_latn": ["kodeks"]}
    assert normalized.match_mode == MATCH_MODE_WORD_PREFIX
    assert normalized.requires == {"any_of": ["fs.test.base"], "signals": ["card"]}


def test_a_draft_without_the_new_fields_keeps_the_historical_defaults() -> None:
    normalized = _draft().normalized()

    assert normalized.exclude == {}
    assert normalized.match_mode == MATCH_MODE_SUBSTRING
    assert normalized.requires is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"match_mode": "prefix"},
        {"exclude": {"en": ["kodeks"]}},
        {"exclude": {"uz_latn": ["ab"]}},
        {"exclude": {"uz_latn": ["regex:("]}},
        {"requires": {"maybe_of": ["fs.test.base"]}},
        {"requires": {"any_of": ["not a rule id"]}},
        {"requires": {"any_of": ["nodots"]}},
        {"requires": {"signals": ["not a signal"]}},
        {"requires": {"any_of": []}},
        {"requires": {"any_of": [f"fs.test.r{index}" for index in range(21)]}},
    ],
)
def test_invalid_precision_drafts_are_rejected(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        _draft(**kwargs).normalized()


async def test_a_stored_precision_override_fires_through_run_rules(rules_factory) -> None:
    async with rules_factory() as session:
        await create_override(
            session,
            _draft(
                rule_id="fs.test.urgency",
                patterns={"uz_latn": ["shoshiling"]},
            ),
        )
        await create_override(
            session,
            _draft(
                rule_id="fs.test.gated",
                patterns={"uz_latn": ["kod"]},
                exclude={"uz_latn": ["kodeks"]},
                match_mode=MATCH_MODE_WORD_PREFIX,
                requires={"any_of": ["fs.test.urgency"]},
            ),
        )
        await session.commit()
        await refresh_rule_pack(session)

    assert "fs.test.gated" not in _fired("kodingizni yuboring")
    assert "fs.test.gated" in _fired("shoshiling, kodingizni yuboring")
    assert "fs.test.gated" not in _fired("shoshiling, jinoyat kodeksi")
    assert "fs.test.gated" not in _fired("shoshiling, bikod")


async def test_a_row_written_before_the_new_columns_loads_as_a_plain_rule(
    rules_factory,
) -> None:
    """NULL columns are what every pre-migration row has; they must read as defaults."""

    async with rules_factory() as session:
        row = await create_override(session, _draft(rule_id="fs.test.legacy"))
        row.exclude = None
        row.match_mode = None
        row.requires = None
        await session.commit()

        definitions, _disabled = await load_overrides(session)

    definition = next(item for item in definitions if item.id == "fs.test.legacy")
    assert definition.exclude == {}
    assert definition.match_mode == MATCH_MODE_SUBSTRING
    assert definition.requires is None


async def test_a_row_with_a_corrupt_precision_field_is_skipped_not_raised(
    rules_factory,
) -> None:
    async with rules_factory() as session:
        good = await create_override(session, _draft(rule_id="fs.test.good"))
        bad = await create_override(session, _draft(rule_id="fs.test.bad"))
        # Written out of band, or before a validation rule existed.
        bad.match_mode = "prefix"
        await session.commit()

        definitions, _disabled = await load_overrides(session)

    assert [definition.id for definition in definitions] == [good.rule_id]


# --- backward compatibility -------------------------------------------------


def test_the_shipped_pack_uses_none_of_the_new_fields() -> None:
    for rule in load_yaml_rule_pack().rules:
        assert rule.exclude == {}, rule.id
        assert rule.match_mode == MATCH_MODE_SUBSTRING, rule.id
        assert rule.requires is None, rule.id


def test_a_rule_with_no_precision_fields_matches_exactly_as_before() -> None:
    rule = _rule("fs.test.legacy", match={"ru": ("код из смс",), "uz_latn": ("sms kod",)})
    _activate(rule)

    assert _fired("Пришлите код из смс прямо сейчас") == {"fs.test.legacy"}
    assert _fired("sms kod keldi") == {"fs.test.legacy"}
    assert _fired("Здравствуйте, во сколько встреча?") == set()
    assert matching_patterns(rule, "Пришлите код из смс") == ("код из смс",)


def test_the_baseline_pack_still_fires_its_rules_end_to_end() -> None:
    fired = _fired("Пришлите код из смс прямо сейчас, это служба безопасности банка")

    assert {"fs.credential.otp", "fs.authority.impersonation"} <= fired
