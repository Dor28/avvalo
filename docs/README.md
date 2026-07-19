# Avvalo — Docs Index

**Avvalo** — *"check before you commit."* An AI assistant for Uzbekistan (Telegram + web) that verifies a **situation, message, document, payment, link, or deal** — in Uzbek or Russian — before a user commits money, identity, or trust. It verifies the *situation, document, or process — never the reputation of a person.*

**On Telegram:** the official bot is **[@Avvalo_official_bot](https://t.me/Avvalo_official_bot)**.

## Current docs

| Doc | What it is |
|---|---|
| [ROADMAP.md](ROADMAP.md) | 🚀 **START HERE for the next work session.** Post-deployment launch roadmap: live-verification checklist (Phase A), numbered launch features R0–R6 with acceptance criteria, launch ops, and evidence gates. Written for handoff to agents; founder-only tasks marked. |
| [LAUNCH_EXECUTOR_PROMPT.md](LAUNCH_EXECUTOR_PROMPT.md) | 🛠️ **Executor handoff for the launch build (R0–R4 + R6)** — code-verified task specs, branch/deploy discipline (build on `launch-features`; merging to `main` deploys), and corrections to stale facts. Give this to the implementing session. |
| [AI_KNOWLEDGE_PIPELINE.md](AI_KNOWLEDGE_PIPELINE.md) | 🧠 **Authoritative R0 execution contract:** local rules and minimization, validated retrieval of reviewed cards/cases, zero-rule semantic analysis, grounding validation, privacy-safe versions, and failure degradation. |
| [PRODUCT_VISION.md](PRODUCT_VISION.md) | 🧭 **Product vision (2026-07-04): "Check · Learn · Share."** Reconciles the original design, the pivot, and the built v1; adds the content/community layer (scam library, curated stories, Scam Pulse) and the legal data-asset story. |
| [PRODUCT_HORIZONS.md](PRODUCT_HORIZONS.md) | 🔭 **3-year option map + ranked feature shortlist.** Tiered future bets — pattern-similarity evidence, voice checks, agentic verification, awareness training, payment-context API, Group Guard, JobPass, sovereign model, escrow — with scoring, hard pull-forward criteria, and the build order (§7). Options, not a to-do list. |
| [ML_RESEARCH.md](ML_RESEARCH.md) | 🔬 **Deep research (2026-07-06): ML capabilities.** Cited build/skip verdicts — embedding similarity vs story corpus (the flagship), URL reputation feeds, SetFit classifier at 300–500 examples; skip screenshot-forensics verdicts, deepfake claims, federated learning. The legal training path = the opt-in story corpus. |
| [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) | ✅ **The authoritative product principles & safety rules — they win on any conflict.** Vision, the shared engine, monetization posture, legal/privacy posture. |
| [V1_TECHNICAL_PLAN.md](V1_TECHNICAL_PLAN.md) | 🧱 **Engineering contract for the built baseline plus T14** — locked stack, contracts, safety validator spec, completed T1–T13 tasks, and the required knowledge-grounding revision. Closest thing to architecture docs. |
| [DEPLOYMENT.md](DEPLOYMENT.md) | 🖥️ **Production ops guide** (Hetzner, hardened Docker, TLS, backups) — the stack currently live. |
| [FAMILY_VALIDATION.md](FAMILY_VALIDATION.md) | ✅ **The alpha contract:** one flow, five golden outputs, retention, cost ceiling, go/pivot/stop gates. Revise the cohort per the PM review before recruiting. |
| [V1_CURRENT_PM_REVIEW.md](V1_CURRENT_PM_REVIEW.md) | 🔎 **Senior-PM review (2026-06-30)** — weak spots and improvement backlog; §6 holds the merchant-discovery interview script the roadmap uses. |

## Historical ([archive/](archive/))

| Doc | Why archived |
|---|---|
| [archive/V1_BUILD_SCOPE.md](archive/V1_BUILD_SCOPE.md) | Scope of the grant-demo build — that build is complete and deployed. |
| [archive/EXECUTOR_PROMPT.md](archive/EXECUTOR_PROMPT.md) | The agent handoff prompt that drove the T1–T13 build — superseded by [ROADMAP.md](ROADMAP.md) §0. |
| [archive/ADJACENT_PRODUCT_IDEAS.md](archive/ADJACENT_PRODUCT_IDEAS.md) | The "check before you commit" reframe + 8 ideas — superseded by [PRODUCT_HORIZONS.md](PRODUCT_HORIZONS.md) as the forward-looking backlog; keeps the market-stat sources and Group Guard detail (§13). |
| [archive/PRODUCT_DESIGN.md](archive/PRODUCT_DESIGN.md) | The graph-era MVP spec. Reusable engine detail; the accusation graph it centers on is permanently retired (see PRODUCT_GUIDE §15). |
| [archive/SESSION_DECISIONS.md](archive/SESSION_DECISIONS.md) | Chronological founding decision log, incl. the 2026-06-21 pivot. |

Removed from the repo entirely (retrieve via git history if ever needed): `USER_STORIES.md`, `FUNDABILITY_AND_GTM.md`, `V1_MVP_PRODUCT_REVIEW.md`, `prompts/fraud_intelligence_startup_prompt.md`.

## Status (2026-07-19)

The deployed v1 baseline remains one engine and two faces — Avvalo + Avvalo Merchants — over Telegram + anonymous web. R0/T14 knowledge-grounded semantic analysis and R6 URL reputation are code-complete with acceptance coverage on `codex/improvement-backlog`, but are not claimed live: production merge still waits for the founder-owned Phase A smoke evidence in [ROADMAP.md](ROADMAP.md).
