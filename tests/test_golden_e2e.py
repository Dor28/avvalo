"""End-to-end execution of the golden fixtures through ``run_check`` (§5.1, §9).

``test_golden_fixtures.py`` validates the *shape* of ``checks.json``; the rule
tests assert that the expected families fire. Neither renders a reply, so the
``must_not_contain`` lists were inert data: a fixture could forbid a phrase that
nothing in the pipeline actually withheld.

This module closes that loop. For every fixture it drives the real pipeline with
an adversarial model that tries to smuggle each forbidden phrase into an
otherwise-valid draft, and asserts the phrase never reaches the user. It is
deliberately indifferent to *how* the phrase is withheld — validator rejection,
retry, or fallback all count — so it constrains observable product behavior
rather than a particular implementation.

Adding a case to ``checks.json`` therefore buys reply-content regression cover,
not only rule-family cover.
"""

import json
from pathlib import Path

import pytest

from app.engine import CheckInput, CheckStatus, InputType, Language, run_check
from app.engine.llm import LLMResponse
from app.engine.rules import load_rule_pack
from app.engine.types import DraftOutput
from tests.support import addressed_rule_ids

GOLDEN_DIR = Path(__file__).resolve().parent / "fixtures" / "golden"


def _fixtures() -> list[dict]:
    return json.loads((GOLDEN_DIR / "checks.json").read_text(encoding="utf-8"))


def _text_fixtures() -> list[dict]:
    return [case for case in _fixtures() if case["input_type"] == "text"]


def _forbidden_cases() -> list[tuple[str, int, str]]:
    """Yield ``(fixture_id, index, forbidden_phrase)`` for every text fixture.

    The index gives each case a stable, collision-free user key without relying
    on ``hash()``, which is salted per interpreter run.
    """

    return [
        (case["id"], index, phrase)
        for case in _text_fixtures()
        for index, phrase in enumerate(case["must_not_contain"])
    ]


def _by_id(fixture_id: str) -> dict:
    return next(case for case in _fixtures() if case["id"] == fixture_id)


class _ScriptedLLM:
    """A model returning a fixed draft, with every supplied rule fact declared.

    ``addressed_rule_ids`` mirrors a compliant model so that rule-preservation
    checks pass and the *only* thing under test is the injected phrase.
    """

    def __init__(self, *, red_flag: str) -> None:
        self.red_flag = red_flag
        self.calls = 0

    async def analyze(self, **kwargs) -> LLMResponse:
        self.calls += 1
        return LLMResponse(
            draft=DraftOutput(
                red_flags=[self.red_flag],
                pattern="pressure to act before checking",
                verify=["Use an official channel you find yourself."],
                ask=["Ask why this cannot wait."],
                addressed_rule_ids=addressed_rule_ids(kwargs["user"]),
            ),
            input_tokens=100,
            output_tokens=50,
        )


async def _run(fixture: dict, llm: _ScriptedLLM, *, user_key: str):
    return await run_check(
        CheckInput(
            user_key=user_key,
            language=Language(fixture["language"]),
            input_type=InputType.text,
            raw_text=fixture["input"],
        ),
        llm_provider=llm,
    )


@pytest.mark.parametrize("fixture_id", [case["id"] for case in _text_fixtures()])
async def test_clean_draft_reaches_the_user(fixture_id: str) -> None:
    """Control: an innocuous draft renders a real reply for every fixture.

    Without this, the adversarial assertions below could pass vacuously — a
    fixture whose draft always failed validation for an unrelated reason would
    never contain a forbidden phrase either.
    """

    fixture = _by_id(fixture_id)
    result = await _run(
        fixture,
        _ScriptedLLM(red_flag="The message pressures an immediate decision."),
        user_key=f"golden-control-{fixture_id}",
    )

    assert result.status is CheckStatus.ok, (
        f"{fixture_id}: control draft did not reach the user "
        f"(status={result.status.value}); adversarial cases would pass vacuously"
    )
    assert result.text


@pytest.mark.parametrize(("fixture_id", "index", "phrase"), _forbidden_cases())
async def test_forbidden_phrase_never_reaches_the_user(
    fixture_id: str, index: int, phrase: str
) -> None:
    """No ``must_not_contain`` phrase may survive into a model-authored reply.

    A ``safety_fallback`` is a pass: the draft was withheld. The fallback copy is
    a reviewed constant that legitimately uses "xavfsiz" about Avvalo's own
    process ("javobni xavfsiz shaklda tayyorlay olmadim"), so it is exempt from a
    ban that targets verdicts about the user's situation.
    """

    fixture = _by_id(fixture_id)
    result = await _run(
        fixture,
        _ScriptedLLM(red_flag=f"Signal noted. {phrase}"),
        user_key=f"golden-adversarial-{fixture_id}-{index}",
    )

    if result.status is not CheckStatus.ok:
        assert result.safety_blocked, (
            f"{fixture_id}: {phrase!r} was withheld but not recorded as a safety block"
        )
        return

    assert phrase.casefold() not in (result.text or "").casefold(), (
        f"{fixture_id}: forbidden phrase {phrase!r} reached the user in an 'ok' reply"
    )


@pytest.mark.parametrize("fixture_id", [case["id"] for case in _text_fixtures()])
async def test_expected_families_survive_to_the_result(fixture_id: str) -> None:
    """The families a fixture expects must appear in the result's rule IDs.

    ``test_rules_and_minimization`` asserts this against ``run_rules`` directly;
    here it is asserted on the ``CheckResult`` the channel actually returns, so a
    regression between matching and result assembly is caught too.
    """

    fixture = _by_id(fixture_id)
    result = await _run(
        fixture,
        _ScriptedLLM(red_flag="The message pressures an immediate decision."),
        user_key=f"golden-families-{fixture_id}",
    )

    families_by_rule = {rule.id: rule.family for rule in load_rule_pack().rules}
    fired = {families_by_rule.get(rule_id) for rule_id in result.rule_ids}
    missing = set(fixture["expected_rule_families"]) - fired
    assert not missing, f"{fixture_id}: families missing from the result: {sorted(missing)}"
