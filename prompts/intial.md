# Project Brief: Avvalo — community scam-protection for Uzbekistan
"Avvalo" = "first / first of all" — the habit we install: AVVALO TEKSHIR
("check first, then pay"). Tagline-ready.

## Mission
Help ordinary people in Uzbekistan avoid getting scammed in Telegram /
marketplace / P2P card-transfer deals. Two user actions: **check** a
suspicious thing, and **report** a scammer. Every report enriches a
crowdsourced scam database — that database is the core long-term asset, so
its quality and structure matter more than anything else in v1.

## Build this (v1 scope)
A Telegram bot backed by an API and a Postgres database, in Uzbek (Latin +
Cyrillic) and Russian.

1. **CHECK** — user sends a phone number, card number, Telegram @username,
   URL/domain, or forwarded message/photo. The system:
   - normalizes input (phone → E.164, strip formatting, mask cards),
   - looks it up against the reports database,
   - returns an **evidence-based result, NOT a vague risk score**, e.g.
     "⚠️ Reported 14 times since March 2026, mostly marketplace prepayment
     scams" or "✅ No reports found — this doesn't prove it's safe, stay
     cautious."
   - always ends with a short, calm safety tip + the reflex line
     "Avvalo tekshir, keyin to'la" ("check first, then pay").

2. **REPORT** — guided, structured intake so data stays clean:
   identifier type + value, scam category (prepayment / fake seller /
   phishing / "Hello Mom" / fake investment / account takeover / other),
   short description, optional screenshot, reporter telegram id
   (for abuse-weighting, never shown publicly).

Plus a minimal admin/moderation interface to review, merge, verify, dismiss
reports and handle disputes.

## Out of scope for v1 (design for, don't build yet)
AI/LLM listing analysis (leave a clean seam for an AI scorer); reverse-image
search (stub the interface); the B2B fraud-intelligence API (design schema +
read-only query layer as if it's coming); any public "wall of shame" naming
individuals.

## Tech stack (I'm a DevOps engineer — ask me before finalizing)
Python (FastAPI) or Node (NestJS); Postgres; Redis for rate-limit/cache;
Telegram Bot API (long-poll dev, webhook-ready prod); fully Dockerized with
docker-compose; 12-factor env config; clean migrations; tests on the core
matching logic.

## Data model (get this right — it's the moat)
- `identifiers` (id, type, normalized_value UNIQUE per type, first_seen,
  report_count, status[active/disputed/cleared], risk_summary)
- `reports` (id, identifier_id FK, reporter_user_id, category, description,
  evidence_url, created_at, weight, status[pending/verified/dismissed])
- `users` (telegram_id, lang, created_at, trust_score, report_quality_stats)
- `checks` (id, querying_user_id, input_type, normalized_value, result,
  created_at) — log every check; valuable behavioral data later.
- `disputes` (id, identifier_id, raised_by, reason, status, created_at)

## Privacy, legal & anti-abuse (non-negotiable — bake in day one)
- Personal-data product. NEVER store full card numbers (mask first6+last4,
  hash rest); treat phones as sensitive PII.
- False-accusation/defamation risk is real: never publicly brand a specific
  person a scammer on a single unverified report; show aggregate evidence
  ("reported N times") only past a configurable threshold; keep individual
  report text internal; provide a dispute path that can mark an identifier
  `disputed` and suppress it.
- Anti-abuse: per-user rate limits (Redis), dedupe repeat reports, weight
  reports by reporter trust_score so one bad actor can't brigade an innocent
  number.
- Built ENTIRELY on public + user-submitted data. No employer systems or
  proprietary feeds — keep this clean and independent.

## Deliverables
Repo as above; README with local-run steps; docker-compose; migrations;
seed script with sample reports; both bot flows working end-to-end on a
local DB; ARCHITECTURE.md marking the seams for the AI scorer, image search,
and B2B API.

Start by proposing the repo structure and the exact DB schema as migrations,
then implement CHECK first (the demo), then REPORT, then moderation. Ask me
about language/framework before coding.
