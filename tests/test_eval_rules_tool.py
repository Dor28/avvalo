"""The rule-evaluation harness and its shipped corpus (PIPELINE_V2 §7)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.eval_rules import (
    Case,
    benign_false_positive_rate,
    evaluate,
    load_corpus,
    main,
    render_report,
)

_CORPUS = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "eval" / "corpus.json"


def _case(**overrides) -> Case:
    base = {
        "id": "c1",
        "text": "hello",
        "language": "uz_latn",
        "expected_rule_ids": frozenset(),
        "benign": True,
    }
    return Case(**{**base, **overrides})


def test_the_shipped_corpus_loads_and_carries_both_halves() -> None:
    cases = load_corpus(_CORPUS)

    assert [case for case in cases if case.benign]
    assert [case for case in cases if not case.benign]
    # The benign half is the precision signal; keep it the larger one.
    assert len([c for c in cases if c.benign]) >= len([c for c in cases if not c.benign])


def test_a_benign_case_may_not_declare_expected_hits(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.json"
    corpus.write_text(
        json.dumps([{"id": "x", "text": "hi", "benign": True, "expected_rule_ids": ["fs.a"]}]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="benign"):
        load_corpus(corpus)


def test_duplicate_case_ids_are_rejected(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.json"
    corpus.write_text(
        json.dumps([{"id": "x", "text": "a"}, {"id": "x", "text": "b"}]), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="duplicate"):
        load_corpus(corpus)


def test_a_rule_firing_on_a_benign_message_is_a_false_positive() -> None:
    cases = [_case(id="benign", text="Hozir SMS orqali kelgan kodni yuboring", benign=True)]

    scores, tripped, _ = evaluate(cases)

    assert tripped
    assert benign_false_positive_rate(cases, tripped) == 1.0
    assert any(score.false_positive for score in scores.values())


def test_an_unlisted_hit_on_a_scam_message_is_not_counted_as_a_false_positive() -> None:
    """Under-labeling a scam case must not look like a precision defect."""

    cases = [
        _case(
            id="scam",
            text="Hozir SMS orqali kelgan kodni yuboring, aks holda hisobingiz yopiladi",
            expected_rule_ids=frozenset({"fs.credential.otp"}),
            benign=False,
        )
    ]

    scores, tripped, _ = evaluate(cases)

    assert not tripped
    assert benign_false_positive_rate(cases, tripped) == 0.0
    assert all(score.false_positive == 0 for score in scores.values())
    assert any(score.unlabeled_on_scam for score in scores.values())


def test_a_missed_expectation_counts_as_a_false_negative() -> None:
    cases = [
        _case(
            id="scam",
            text="Bugun ob-havo yaxshi.",
            expected_rule_ids=frozenset({"fs.credential.otp"}),
            benign=False,
        )
    ]

    scores, _tripped, _ = evaluate(cases)

    assert scores["fs.credential.otp"].false_negative == 1
    assert scores["fs.credential.otp"].recall == 0.0


def test_the_report_names_the_benign_messages_that_tripped_a_rule() -> None:
    cases = [_case(id="benign_otp", text="Hozir kodni yuboring", benign=True)]
    scores, tripped, unexpected = evaluate(cases)

    report = render_report(cases, scores, tripped, unexpected)

    assert "benign_otp" in report
    assert "benign false-positive rate" in report


def test_the_tool_fails_when_the_benign_rate_exceeds_the_threshold(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.json"
    corpus.write_text(
        json.dumps(
            [{"id": "b", "text": "Hozir SMS kodni yuboring", "benign": True}]
        ),
        encoding="utf-8",
    )

    assert main(["--corpus", str(corpus), "--max-fp-rate", "0.0"]) == 1
    assert main(["--corpus", str(corpus), "--max-fp-rate", "1.0"]) == 0


def test_a_missing_corpus_is_reported_rather_than_raised(tmp_path: Path) -> None:
    assert main(["--corpus", str(tmp_path / "nope.json")]) == 2
