# Avvalo — Documentation Index

> **Last updated:** 2026-07-22

The repository has one product direction and one active roadmap. Historical and superseded
documents were removed; Git history remains the source for old decisions.

## Product authority

| Order | Document | Purpose |
|---:|---|---|
| 1 | [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) | Canonical product, features, evidence boundary, privacy, and non-goals |
| 2 | [ROADMAP.md](ROADMAP.md) | Current order: editorial cases, manual Verify validation, strict MVP, measured alpha |
| 3 | [VERIFY_VALIDATION.md](VERIFY_VALIDATION.md) | Manual experiment, source inventory, and go/stop gates |

No other document may introduce a feature or change priority.

## Technical contracts

| Document | Purpose |
|---|---|
| [V1_TECHNICAL_PLAN.md](V1_TECHNICAL_PLAN.md) | Current implemented architecture and engineering constraints |
| [AI_KNOWLEDGE_PIPELINE.md](AI_KNOWLEDGE_PIPELINE.md) | Rules, minimization, reviewed knowledge, LLM, and safety validation |
| [tasks/](tasks/README.md) | Executor-ready tasks created only when the roadmap gate permits implementation |

## Current status

The built baseline accepts suspicious text and images through Telegram and web, explains supported
risk signals, and suggests independent verification steps. Seller, payment, courier, and refund
situations use the same checker. There is no separate merchant product, public scam library, story
capture, or Scam Pulse.

The next proposed capability is Avvalo Verify. It is not built or live until the validation gate,
implementation acceptance and automated checks pass.
