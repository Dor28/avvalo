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
| Rules | `app/engine/rules/`, `rules/checker/` | Deterministic local signals |
| Rule overrides | `app/rules_store/` | Operator-authored patterns merged onto the baseline |
| Card overrides | `app/knowledge_store/` | Operator-authored cards merged onto the baseline |
| Minimization | `app/engine/minimize.py` | Removes PII before model calls |
| Knowledge | `app/engine/knowledge/`, `knowledge/checker/` | Reviewed explanatory guidance |
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
3. Resolve the response language: `uz_latn`, `uz_cyrl`, or `ru`.
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

`rules/checker/families.yaml` is the shipped baseline rule pack. Stable `fs.*` rule IDs must not be
renamed because events, knowledge cards, tests, and sanitized Share summaries reference them.

The pack covers credential theft, urgency/secrecy, authority impersonation, upfront payment,
verification avoidance, implausible promises, suspicious links/QR codes, incoming-payment receipt
inconsistency, screenshot claims, overpayment/refund requests, and pressure to release goods.

A screenshot, receipt, or message never proves that an incoming payment arrived. Relevant output
must tell the user to verify the matching transfer independently in the receiving bank/payment
account before refunding money or releasing goods.

### 5.1 Operator rule overrides

The repository is public, so its keyword lists are readable by the people they detect. New pattern
work therefore lives in the `rule_override` table (`app/rules_store/`) rather than in git, on its
own declarative base beside `EditorialBase` — patterns are operator-authored reference data, never
user content, and must stay outside the zero-content contract enforced over `app.data.models.Base`.

Overrides merge onto the baseline **by rule ID**: a matching ID replaces that rule, a new ID adds
one, and a `disabled` row suppresses a baseline rule. Wholesale replacement was rejected because it
would force an operator to re-enter the entire pack before adding one keyword.

`load_rule_pack()` stays synchronous and is served from a process-level snapshot, because the pack
is read several times per check and from inside the formatter and prompt builder.
`app.rules_store.apply` refreshes that snapshot every `RULE_PACK_REFRESH_MINUTES` on the existing
scheduler. Both failure paths are deliberately fail-safe: an unreachable database leaves the
previously published pack in force and ultimately falls back to the shipped YAML baseline, and a
single malformed row is skipped rather than taking the whole pack down. Patterns are validated on
write — regexes must compile and literals must clear a minimum length — because a bad pattern
degrades detection silently for every user.

Moving patterns out of git does not retract what is already published; it only keeps future work
unpublished.

## 6. Knowledge and model boundary

Only approved, versioned cards from `knowledge/checker/cards.yaml` may be retrieved. Cards explain
patterns and verification steps; they are not official-source evidence and cannot establish
identity, intent, or fraud.

The semantic router is optional and receives minimized text plus a server-generated allowlist. It
may select only allowed card IDs. Empty or unavailable knowledge must degrade safely to the rule and
signal context.

### 6.1 Operator card overrides

Cards follow the same posture as rule patterns (§5.1): new card work lives in the
`knowledge_card_override` table (`app/knowledge_store/`) rather than in the public repository, on
its own declarative base, and merges onto the shipped `knowledge/<face>/cards.yaml` base **by card
ID**. A `draft` or `retired` override suppresses the baseline card of that ID.

`KnowledgeStore.load()` stays synchronous and is served from a process-level snapshot refreshed
every `KNOWLEDGE_REFRESH_MINUTES`. An unreachable database leaves the previous base in force and
ultimately falls back to the YAML baseline; a single malformed row is skipped. Degrading to an
*empty* base is specifically not acceptable, because `retrieval_status` would then read `empty`
rather than `unavailable` and the pipeline would look healthy while answering with no knowledge.

When an override contributes, `kb_version` becomes `<base-version>.db<YYYYMMDDHHMMSS>`. The format
is constrained by `app/data/repo.py`'s `VERSION_RE`, which rejects a bad `kb_version` on every
`check_event` write — `+`, `:` and spaces are not permitted.

The full knowledge contract lives in
[AI_KNOWLEDGE_PIPELINE.md](AI_KNOWLEDGE_PIPELINE.md).

## 7. Persistence and privacy

Active tables contain consent, check-event metadata, categorical feedback, rate limits, deletion
audit rows, and hash-only URL reputation entries. `user_key` is derived with HMAC; raw Telegram IDs
are not stored or logged.

Founder-authored public cases live in the separate `editorial_post` table and
`app.content.models.EditorialBase`. Every record contains three deliberately authored language
versions plus draft/publication metadata. No user key or submitted check content enters this table,
and editorial rows are not part of `/delete_my_data` because they are operator-owned public content.

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

`GET /cases` and `GET /cases/{slug}` expose published editorial cases only. `/admin` is disabled
unless `ADMIN_ACCESS_KEY` is configured. When enabled, a short-lived signed HttpOnly cookie protects
the founder dashboard and trilingual editor; same-origin checks cover every admin write. Drafts are
never returned by public routes. Post bodies are rendered as escaped plain text, not trusted HTML.

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
