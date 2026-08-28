"""Measure rule-layer precision against a labeled corpus (PIPELINE_V2 §7).

Run it from the repository root::

    python -m tools.eval_rules
    python -m tools.eval_rules --corpus path/to/corpus.json --max-fp-rate 0.05

Reports per-rule precision and recall over the labeled cases, plus the
false-positive rate on the benign half — the number that keeps a keyword change
from buying recall by carpet-bombing ordinary messages. Exits non-zero when that
rate exceeds the threshold, so the regression is visible in CI rather than in
production answers.

The corpus is ordinary test data, never user submissions: checks are ephemeral
by design and must stay that way.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from app.engine.rules import run_rules

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_CORPUS = _REPO_ROOT / "tests" / "fixtures" / "eval" / "corpus.json"
_DEFAULT_MAX_FP_RATE = 0.05


@dataclass(frozen=True)
class Case:
    """One labeled corpus entry."""

    id: str
    text: str
    language: str
    expected_rule_ids: frozenset[str]
    benign: bool


@dataclass
class RuleScore:
    """Per-rule confusion counts across the corpus.

    Unexpected firings are split by the kind of case they happened on, because
    the two mean opposite things. Firing on a **benign** message is a real
    false positive: an ordinary message was flagged. Firing on a **scam**
    message that simply did not list this rule is almost always a gap in the
    label, not a defect — the message really is a scam and the rule really does
    describe part of it. Only the first kind is a precision signal, so only the
    first kind is counted in ``precision`` and gates the run.
    """

    true_positive: int = 0
    false_positive: int = 0
    unlabeled_on_scam: int = 0
    false_negative: int = 0

    @property
    def precision(self) -> float | None:
        fired = self.true_positive + self.false_positive
        return self.true_positive / fired if fired else None

    @property
    def recall(self) -> float | None:
        expected = self.true_positive + self.false_negative
        return self.true_positive / expected if expected else None


def load_corpus(path: Path) -> list[Case]:
    """Read and validate the labeled corpus."""

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"{path}: expected a list of cases")

    cases: list[Case] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw):
        case_id = str(entry.get("id") or f"case-{index}")
        if case_id in seen:
            raise ValueError(f"{path}: duplicate case id {case_id!r}")
        seen.add(case_id)
        benign = bool(entry.get("benign", False))
        expected = frozenset(entry.get("expected_rule_ids") or ())
        if benign and expected:
            raise ValueError(
                f"{path}: case {case_id!r} is benign but expects rule hits"
            )
        cases.append(
            Case(
                id=case_id,
                text=str(entry["text"]),
                language=str(entry.get("language", "uz_latn")),
                expected_rule_ids=expected,
                benign=benign,
            )
        )
    return cases


def evaluate(cases: list[Case]) -> tuple[dict[str, RuleScore], list[Case], list[str]]:
    """Score every case, returning per-rule counts and the benign misfires."""

    scores: dict[str, RuleScore] = defaultdict(RuleScore)
    tripped_benign: list[Case] = []
    unexpected_on_benign: list[str] = []

    for case in cases:
        hits, _signals = run_rules(case.text)
        fired = {hit.rule_id for hit in hits}

        for rule_id in fired & case.expected_rule_ids:
            scores[rule_id].true_positive += 1
        for rule_id in fired - case.expected_rule_ids:
            if case.benign:
                scores[rule_id].false_positive += 1
            else:
                scores[rule_id].unlabeled_on_scam += 1
        for rule_id in case.expected_rule_ids - fired:
            scores[rule_id].false_negative += 1

        if case.benign and fired:
            tripped_benign.append(case)
            unexpected_on_benign.extend(sorted(fired))

    return dict(scores), tripped_benign, unexpected_on_benign


def _format_rate(value: float | None) -> str:
    return "    n/a" if value is None else f"{value * 100:6.1f}%"


def render_report(
    cases: list[Case],
    scores: dict[str, RuleScore],
    tripped_benign: list[Case],
    unexpected_on_benign: list[str],
) -> str:
    benign = [case for case in cases if case.benign]
    labeled = [case for case in cases if not case.benign]
    fp_rate = len(tripped_benign) / len(benign) if benign else 0.0

    lines = [
        "Avvalo rule-layer evaluation",
        "=" * 77,
        f"cases: {len(cases)}  ({len(labeled)} labeled, {len(benign)} benign)",
        "",
        "fp  = fired on a benign message (a real false positive)",
        "unl = fired on a scam message that did not list the rule (usually a label gap)",
        "",
        f"{'rule_id':<34}{'prec':>8}{'recall':>9}{'tp':>5}{'fp':>5}{'fn':>5}{'unl':>5}",
        "-" * 77,
    ]
    for rule_id in sorted(scores):
        score = scores[rule_id]
        lines.append(
            f"{rule_id:<34}"
            f"{_format_rate(score.precision):>8}"
            f"{_format_rate(score.recall):>9}"
            f"{score.true_positive:>5}{score.false_positive:>5}"
            f"{score.false_negative:>5}{score.unlabeled_on_scam:>5}"
        )
    if not scores:
        lines.append("(no rule fired and none was expected)")

    lines += [
        "-" * 77,
        "",
        f"benign false-positive rate: {fp_rate * 100:.1f}% "
        f"({len(tripped_benign)}/{len(benign) or 0} ordinary messages tripped a rule)",
    ]
    if tripped_benign:
        lines.append("")
        lines.append("benign messages that fired a rule:")
        for case in tripped_benign:
            hits, _ = run_rules(case.text)
            fired = ", ".join(sorted(hit.rule_id for hit in hits))
            lines.append(f"  - {case.id} [{case.language}] -> {fired}")
        counts = defaultdict(int)
        for rule_id in unexpected_on_benign:
            counts[rule_id] += 1
        lines.append("")
        lines.append("rules most responsible:")
        for rule_id, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"  - {rule_id}: {count}")
    return "\n".join(lines)


def benign_false_positive_rate(cases: list[Case], tripped_benign: list[Case]) -> float:
    benign = [case for case in cases if case.benign]
    return len(tripped_benign) / len(benign) if benign else 0.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=_DEFAULT_CORPUS)
    parser.add_argument(
        "--max-fp-rate",
        type=float,
        default=_DEFAULT_MAX_FP_RATE,
        help="fail when the benign false-positive rate exceeds this (default 0.05)",
    )
    args = parser.parse_args(argv)

    if not args.corpus.exists():
        print(f"corpus not found: {args.corpus}", file=sys.stderr)
        return 2

    cases = load_corpus(args.corpus)
    scores, tripped_benign, unexpected = evaluate(cases)
    print(render_report(cases, scores, tripped_benign, unexpected))

    fp_rate = benign_false_positive_rate(cases, tripped_benign)
    if fp_rate > args.max_fp_rate:
        print(
            f"\nFAIL: benign false-positive rate {fp_rate * 100:.1f}% "
            f"exceeds the {args.max_fp_rate * 100:.1f}% threshold",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
