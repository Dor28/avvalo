# Avvalo — Documentation Index

> **Last updated:** 2026-08-29

The repository has one product direction and one active roadmap. Historical and superseded
documents were removed; Git history remains the source for old decisions.

## Product authority

| Order | Document | Purpose |
|---:|---|---|
| 1 | [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) | Canonical product, capabilities, answer contract, privacy, and non-goals |
| 2 | [ROADMAP.md](ROADMAP.md) | Current order of work: the scanner answer, the application, reach, distribution — plus the parallel content track |

No other document may introduce a feature or change priority.

## Technical contracts

| Document | Purpose |
|---|---|
| [V1_TECHNICAL_PLAN.md](V1_TECHNICAL_PLAN.md) | Current implemented architecture and engineering constraints |
| [AI_KNOWLEDGE_PIPELINE.md](AI_KNOWLEDGE_PIPELINE.md) | Rules, minimization, reviewed knowledge, LLM, and safety validation |
| [PIPELINE_V2.md](PIPELINE_V2.md) | Answer grounding, rule precision fields, and the evaluation corpus |
| [tasks/](tasks/README.md) | Executor-ready tasks created only when the roadmap permits implementation |

## Parked

| Document | Why |
|---|---|
| [VERIFY_VALIDATION.md](VERIFY_VALIDATION.md) | Avvalo Verify — typed facts from official registries. Parked, not cancelled; see PRODUCT_GUIDE §9. No implementation task may be written for it |

## Current status

Built: Telegram and anonymous web intake, OCR, local QR decoding, one URL analyzer, the
deterministic rule layer, PII minimization, the LLM explanation behind a safety validator,
database-backed rule and card overrides with founder editors, the Knowledge section, retention
and deletion.

Not built: the Telegram Mini App, the short scanner answer, redirect resolution, Cyrillic-Uzbek
output, wave notifications, first-run examples, the forwardable reminder, family-group behaviour,
and inline mode. ROADMAP holds the order.

Detection assets are thin — 13 rules, 10 knowledge cards, 14 catalog organizations, 13 golden
cases, all universal patterns rather than local ones. The content track in ROADMAP §6 is what
closes that gap, and no product surface compensates for its absence.
