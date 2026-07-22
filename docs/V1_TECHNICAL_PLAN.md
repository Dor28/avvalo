# Avvalo — Current Technical Contract

> **Status:** Authoritative description of the implemented baseline · 2026-07-22
>
> **Product authority:** [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md)
> **Execution order:** [ROADMAP.md](ROADMAP.md)

This document describes the code that is allowed to exist now. It is not a backlog and does not
preserve retired product ideas. Historical designs remain available in Git history.

## 1. System boundary

Avvalo is one consumer product with two thin channels:

- Telegram bot;
- anonymous web checker.

Both channels accept suspicious text or an image/screenshot and call the same `run_check()` engine.
The internal face ID remains `family` for database and rule-ID compatibility. It is the only active
face. Payment screenshots, seller situations, courier pressure, and refund requests use this same
flow.

The product does not provide accounts, history, person/entity lookup, accusations, verdicts, risk
scores, merchant mode, public content pages, story capture, trend publishing, or general browsing.
Avvalo Verify is not implemented until the validation gate in
[VERIFY_VALIDATION.md](VERIFY_VALIDATION.md) passes.

## 2. Runtime architecture

One Python process runs:

- aiogram long-polling for Telegram;
- FastAPI for the optional web channel;
- APScheduler retention and maintenance jobs;
- one shared async SQLAlchemy engine and session factory.

Production uses PostgreSQL. Tests use SQLite where practical. The production Compose stack adds
nginx and certbot; PostgreSQL is not exposed publicly.

Important modules:

| Area | Location | Responsibility |
|---|---|---|
| Engine | `app/engine/pipeline.py` | Orchestrates every check |
| Types | `app/engine/types.py` | Boundary enums and Pydantic models |
| Rules | `app/engine/rules/`, `rules/family/` | Deterministic local signals |
| Minimization | `app/engine/minimize.py` | Removes PII before model calls |
| Knowledge | `app/engine/knowledge/`, `knowledge/family/` | Reviewed explanatory guidance |
| LLM | `app/engine/llm/` | OpenAI-compatible provider boundary and fallback |
| Safety | `app/engine/validate.py` | Deterministic output validation |
| Telegram | `app/bot/` | Consent, intake, result, feedback, Share |
| Web | `app/web/` | Anonymous intake and result rendering |
| Persistence | `app/data/` | Metadata-only ORM, repository, retention |
| Observability | `app/obs/` | Allowlisted events, metrics, alerts |

## 3. Check pipeline

Every accepted request follows this order:

1. Confirm current consent and reserve the applicable daily limit.
2. Read text, or preprocess the image and run OCR.
3. Resolve the response language: `uz_latn` or `ru` (Cyrillic-Uzbek resolves to `uz_latn`).
4. Run local rules and structural signal extraction on local text.
5. Optionally check URL hashes against the local reputation table.
6. Minimize PII and identifiers.
7. Retrieve at most three approved knowledge cards; optionally use the allowlisted semantic router.
8. Call the configured answer model, with one configured provider fallback.
9. Validate structure, grounding, prohibited claims, verdict words, contacts, and rule preservation.
10. Retry once after validation failure; otherwise return the localized safety fallback.
11. Format the localized result and persist only allowlisted metadata.

Non-billable failures refund the reserved limit. Channels do not duplicate engine logic.

## 4. Core contracts

### Input

`CheckInput` carries:

- `face="family"`;
- pseudonymous `user_key`;
- `language`;
- `input_type` (`text` or `image`);
- ephemeral `raw_text`, `image_bytes`, and `caption`.

Ephemeral content must never enter a database row, log, event, alert, metric, cache, or output file.

### Output

Successful model output contains short localized blocks for:

- concrete red flags, if supported by detected evidence;
- the pattern or mechanism;
- independent verification steps;
- questions the user can ask.

The validator rejects person-level conclusions, `safe`/`scam`/`fraud confirmed`, numerical risk
scores, fabricated contacts, claimed external checks, leaked internal IDs, unsupported links, and
missing authoritative rule coverage.

### Statuses

The engine uses categorical statuses such as `ok`, `no_signal`, `empty_input`, `low_ocr`,
`rate_limited`, `timeout`, `llm_error`, `ocr_error`, `unsupported_media`, and `safety_fallback`.
Error classes are categorical identifiers, never exception messages.

## 5. Rules and payment protection

`rules/family/families.yaml` is the sole active rule pack. Stable `fs.*` rule IDs must not be
renamed because events, knowledge cards, tests, and sanitized Share summaries reference them.

The pack covers credential theft, urgency/secrecy, authority impersonation, upfront payment,
verification avoidance, implausible promises, suspicious links/QR codes, incoming-payment receipt
inconsistency, screenshot claims, overpayment/refund requests, and pressure to release goods.

A screenshot, receipt, or message never proves that an incoming payment arrived. Relevant output
must tell the user to verify the matching transfer independently in the receiving bank/payment
account before refunding money or releasing goods.

## 6. Knowledge and model boundary

Only approved, versioned cards from `knowledge/family/cards.yaml` may be retrieved. Cards explain
patterns and verification steps; they are not official-source evidence and cannot establish
identity, intent, or fraud.

The semantic router is optional and receives minimized text plus a server-generated allowlist. It
may select only allowed card IDs. Empty or unavailable knowledge must degrade safely to the rule and
signal context.

The full knowledge contract lives in
[AI_KNOWLEDGE_PIPELINE.md](AI_KNOWLEDGE_PIPELINE.md).

## 7. Persistence and privacy

Active tables contain consent, check-event metadata, categorical feedback, rate limits, deletion
audit rows, and hash-only URL reputation entries. `user_key` is derived with HMAC; raw Telegram IDs
are not stored or logged.

`story_submission` is a legacy stewardship-only table:

- no active route, handler, repository API, or tool writes or reads it as product data;
- `/delete_my_data` still deletes matching legacy rows;
- retention still removes rejected legacy rows under the configured policy;
- dropping the table or purging remaining data requires a separately authorized migration.

`log_event()` and `log_error()` accept only allowlisted categorical metadata. Submitted content,
OCR text, model output, URLs, contacts, and exception strings are forbidden.

## 8. Channel behavior

### Telegram

`/start` selects language and presents the current privacy notice. Content is processed only after
the current notice version is accepted. The bot returns the formatted result, check-bound
categorical feedback buttons, and a sanitized Share action. `/privacy` and `/delete_my_data` remain
available.

### Web

`GET /` and `GET /check` render the same anonymous checker. `POST /check` always builds the active
`family` input. Uploads are size/pixel limited, kept ephemeral, same-origin protected, and image
checks require Turnstile when configured. Session and IP-derived keys are pseudonymous.

`/merchants` is only a `308` compatibility redirect to `/check`. `/scams` and `/sitemap.xml` are not
product routes. `/healthz` checks process liveness; `/readyz` also checks database connectivity.

## 9. Observability and operator tools

Operational metrics and feedback-label reports read active `family` events only. They expose
aggregate counts, statuses, languages, cost/latency, no-signal rate, safety fallback counts,
knowledge coverage, and categorical feedback without user keys or check IDs.

Supported tools include:

```bash
python -m app.tools.metrics
python -m app.tools.metrics --days 30
python -m app.tools.metrics labels --since 2026-07-01
python -m app.tools.knowledge_gaps --days 7 --face family
python tools/eval_models.py
```

There is no Scam Pulse export or story-review CLI.

## 10. Configuration and deployment

Configuration is validated by `app/config.py` from environment variables. Examples live in
`.env.example` and `deploy/env.prod.example`. Runtime secrets must never be committed.

The relevant deployment sources are:

- `Dockerfile`;
- `docker-compose.yml` for local development;
- `docker-compose.prod.yml` for production;
- `.github/workflows/deploy.yml`;
- `deploy/` for nginx, TLS bootstrap, update, backup, and restore helpers.

Pushing `main` triggers production deployment. Integration therefore requires a green release
check and explicit authorization.

## 11. Definition of done

For every runtime change:

```bash
pytest -q
ruff check .
git diff --check
python tools/secret_scan.py --all
alembic heads
docker compose config
docker compose -f docker-compose.prod.yml \
  --env-file deploy/env.prod.example config --no-env-resolution --quiet
```

The current baseline is acceptable only while:

- Telegram and web call the same engine;
- all user-facing copy exists in all three languages;
- no active path persists or logs submitted content;
- outputs remain non-verdict, grounded, and independently verifiable;
- the single active face and its deployed rules/knowledge assets load successfully;
- consent, deletion, retention, rate limits, Share, feedback, and readiness checks remain green.
