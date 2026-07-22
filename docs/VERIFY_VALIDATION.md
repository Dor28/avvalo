# Avvalo Verify — Validation Spec

> **Status:** Active product experiment
> **Last updated:** 2026-07-22
> **Authority:** [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md)

## 1. Decision

This experiment answers one question:

> Does source-backed verification make Avvalo materially more useful than advice alone?

It does not test future products, community content, merchants, voice, group monitoring, or a
revenue model.

## 2. Scope

Test exactly three verification families:

1. official identity match;
2. link and QR evidence;
3. regulated organization and license routing.

Do not write feature code during the concierge stage. Produce every answer manually from the same
source and evidence rules the eventual system would follow.

## 3. Validation packet

The founder-reviewed packet contains 30 representative scenarios:

| Family | Scenarios | Language coverage |
|---|---:|---|
| Official identity match | 10 | all three language forms |
| Link and QR evidence | 10 | all three language forms |
| Register/license routing | 10 | all three language forms |

Each scenario records a minimized test situation, the artifact to check, exact source and access
method, expected typed status, decision-relevant fact, limitations, advice-only answer,
evidence-backed answer, and whether the evidence could change the next action.

Use synthetic or founder-authored scenarios by default. Real participant content may be viewed only
in a consented live session and must not be retained.

## 4. Source inventory

Every proposed source has a reviewed row:

| Field | Requirement |
|---|---|
| Owner | Organization responsible for the source |
| Source URL | Direct official page, dataset, or register |
| Claim supported | Exact bounded fact the source can establish |
| Access method | Curated catalog, local snapshot, permitted API, or user-routed deep link |
| Data transmitted | Exact artifact sent outside Avvalo, if any |
| Terms | Known permission, restriction, or unresolved question |
| Freshness | Refresh interval and stale-data behavior |
| Failure behavior | Always `unavailable`; never guess |
| Display wording | Deterministic wording in all three language forms |

Exclude a source with unresolved permission, unsafe data transfer, or undefined failure behavior.

## 5. Paired user test

Recruit participants who have encountered suspicious digital situations in Uzbekistan. Show paired
answers for several scenarios in randomized order:

- version A: red flags, independent checks, and questions;
- version B: the same answer plus a valid source-backed evidence block.

Ask which answer they trust and find more useful, whether it changes their next action, whether any
fact sounds stronger than its source, and whether they would submit a similar real situation.

Record categorical responses only. Do not retain participant messages, screenshots, links,
contacts, or identifiers.

## 6. Concierge gate

Proceed to an implementation spec only when all conditions pass:

- **Evidence coverage:** at least 12 of 30 scenarios (40%) yield a decision-relevant source fact.
- **Preference:** at least 70% of participants prefer the evidence-backed answer.
- **Integrity:** zero invented, overstated, unsourced, or person-level facts.

Decision:

- `go` — all conditions pass;
- `revise once` — integrity passes but coverage or preference narrowly misses; change one major
  variable and repeat once;
- `stop` — integrity fails, or the second test still misses coverage/preference.

Do not add a fourth verification family to rescue a failed result.

## 7. MVP acceptance after a go decision

The implementation must:

- support only the three validated families;
- emit `supported`, `exact_mismatch`, `not_found`, or `unavailable`;
- attach source, observation time, and limitations to every fact;
- fail closed when a source is stale, down, or malformed;
- keep submitted artifacts ephemeral;
- prevent the LLM from inventing or altering evidence;
- render all output in `uz_latn`, `uz_cyrl`, and `ru`;
- pass adversarial tests for lookalike domains, punycode, deceptive subdomains, stale snapshots,
  missing records, source outages, and prompts that demand a verdict.

## 8. Measured alpha

Minimum sample:

- 60 activated users;
- 150 completed real checks;
- 30 users with a full 14-day opportunity to return;
- all three language forms and text/image input represented;
- at least 30 supervised or explicitly consented evidence-quality audits.

| Metric | Pass condition |
|---|---:|
| Evidence coverage | at least 35% of completed checks |
| Audited fact precision | at least 98% |
| Critical false facts | 0 |
| Evidence usefulness | at least 70% |
| Decision impact | at least 25% |
| Facts with source and observation time | 100% |
| Privacy incidents | 0 |
| Person-level verdicts | 0 |
| Blended variable cost per successful check | at most $0.03 |

Evidence coverage means a completed check had at least one useful, valid source fact. Decorative
lookups do not count.

## 9. Privacy-safe measurement

Events may store pseudonymous IDs, language, input type, verification family, typed status, source
ID, snapshot version, latency, cost, and categorical feedback. They may not store submitted text,
OCR text, URLs, domains, contacts, payment details, names, screenshots, prompts, or answers.

Quality review uses synthetic cases or one-time participant consent in a live session. Hidden
content logging is prohibited.

## 10. Completion

The experiment is complete when the packet and source inventory are reviewed, paired sessions are
complete, the concierge gate has a written decision, any approved MVP passes acceptance, the alpha
reaches its sample, and the founder records `continue`, `revise once`, or `stop`.

No feature becomes active merely because it appears in an older document.
