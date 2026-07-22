# Avvalo — Documentation Index

> **Last updated:** 2026-07-22

There is one active product direction and one active roadmap. Read only the first three documents
to understand what Avvalo is and what happens next.

## Active product documents

| Order | Document | Authority |
|---:|---|---|
| 1 | [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) | Canonical product, feature set, evidence boundary, privacy, and non-goals |
| 2 | [ROADMAP.md](ROADMAP.md) | Current sequence: baseline smoke → manual Verify validation → strict MVP → measured alpha |
| 3 | [VERIFY_VALIDATION.md](VERIFY_VALIDATION.md) | The 30-scenario experiment, source inventory, and go/stop gates |

No other document may introduce a feature or change priority.

## Active technical references

| Document | Purpose |
|---|---|
| [V1_TECHNICAL_PLAN.md](V1_TECHNICAL_PLAN.md) | Implemented baseline architecture. Legacy merchant code remains documented as code, not product direction. |
| [AI_KNOWLEDGE_PIPELINE.md](AI_KNOWLEDGE_PIPELINE.md) | Rules, minimization, reviewed knowledge, LLM, and safety validation. Knowledge guidance is not official-source evidence. |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Production deployment and operations |
| [ops/SMOKE_2026-07.md](ops/SMOKE_2026-07.md) | Evidence checklist for the current production deployment |
| [tasks/](tasks/README.md) | Executor-ready tasks. No Avvalo Verify build task exists until validation passes. |

## Historical implementation records

- [IMPROVEMENT_BACKLOG.md](IMPROVEMENT_BACKLOG.md) records earlier engine hardening work. It is not
  the current backlog.
- [FAMILY_VALIDATION.md](FAMILY_VALIDATION.md) is a legacy link that redirects to the Verify
  experiment.
- [PRODUCT_VISION.md](PRODUCT_VISION.md), [PRODUCT_HORIZONS.md](PRODUCT_HORIZONS.md),
  [V1_CURRENT_PM_REVIEW.md](V1_CURRENT_PM_REVIEW.md), [ML_RESEARCH.md](ML_RESEARCH.md), and
  [LAUNCH_EXECUTOR_PROMPT.md](LAUNCH_EXECUTOR_PROMPT.md) are superseded pointers, not plans.
- [archive/](archive/README.md) contains older designs and decisions. It must never drive current scope.

## Current product status

The built baseline accepts suspicious text and images through Telegram and web, explains red flags,
and suggests independent verification steps. The next proposed capability is Avvalo Verify: bounded,
source-backed facts for official identity, links/QR codes, and regulated-organization/license
routing.

Avvalo Verify is not considered built or live until its validation gate, implementation acceptance,
and deployment smoke checks pass.
