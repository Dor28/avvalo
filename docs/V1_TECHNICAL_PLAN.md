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
There is no internal product-face ID: it was removed from the code and the schema in migration
`0007_drop_face`. Payment screenshots, seller situations, courier pressure, and refund requests use this same
flow.

The product does not provide accounts, history, person/entity lookup, accusations, verdicts, risk
scores, merchant mode, story capture, trend publishing, or general browsing. No code path fetches,
renders, or executes a submitted destination; the one bounded exception is shortener redirect
resolution under [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) §8.1, which is specified but not yet
implemented.

Avvalo Verify is **parked** (PRODUCT_GUIDE §9). If it is ever taken off the shelf, the validation
gate in [VERIFY_VALIDATION.md](VERIFY_VALIDATION.md) passes first.

Capabilities described in PRODUCT_GUIDE §4 but not yet in this contract — the Telegram Mini App,
the short scanner answer, redirect resolution, Cyrillic-Uzbek output, wave notifications — are
scheduled in [ROADMAP.md](ROADMAP.md). This document describes what exists, not what is planned.

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
| Rules | `app/engine/rules/`, `rules/*.yaml` | Deterministic local signals |
| Rule overrides | `app/rules_store/` | Operator-authored patterns merged onto the baseline |
| Card overrides | `app/knowledge_store/` | Operator-authored cards merged onto the baseline |
| Minimization | `app/engine/minimize.py` | Builds strict retrieval text and a protected answer-prompt view |
| Knowledge | `app/engine/knowledge/`, `knowledge/cards/` | Reviewed explanatory guidance |
| LLM | `app/engine/llm/` | OpenAI-compatible provider boundary and fallback |
| Safety | `app/engine/validate.py` | Deterministic output validation |
| Telegram | `app/bot/` | Consent, intake, result, feedback, Share |
| Web | `app/web/` | Anonymous intake and result rendering |
| Persistence | `app/data/` | Metadata-only ORM, repository, retention |
| Observability | `app/obs/` | Allowlisted events, metrics, alerts |

## 3. Check pipeline

Every accepted request follows this order:

1. Confirm current consent and reserve the applicable daily limit.
2. Read text, or preprocess the image and locally decode QR symbols beside OCR. A single decoded
   payload joins the same ephemeral text path; EMVCo-shaped payment payloads become only a typed
   signal, and multiple codes return retry guidance instead of an arbitrary choice.
3. Resolve the response language: `uz_latn` or `ru` (Cyrillic-Uzbek resolves to `uz_latn`).
4. Run local rules and structural signal extraction on local text.
5. Build strict retrieval text, then a protected answer-prompt view that retains submitted names
   and full URLs while tokenizing phones, cards, credentials, codes, passports, addresses, and
   other protected identifiers. Decoded QR payloads remain strictly minimized.
6. Retrieve at most three approved knowledge cards; optionally use the allowlisted semantic router.
7. Call the configured answer model, with one configured provider fallback.
8. Validate structure, grounding, prohibited claims, verdict words, contacts, and rule preservation.
9. Retry once after validation failure; otherwise return the localized safety fallback.
10. Format the localized result and persist only allowlisted metadata.

Non-billable failures refund the reserved limit. Channels do not duplicate engine logic.

## 4. Core contracts

### Input

`CheckInput` carries:

- pseudonymous `user_key`;
- `language`;
- `input_type` (`text` or `image`);
- ephemeral `raw_text`, `image_bytes`, and `caption`.

Ephemeral content, including locally decoded QR payloads, must never enter a database row, log,
event, alert, metric, cache, or output file.

### Output

Successful model output contains short localized blocks for:

- concrete red flags, if supported by detected evidence;
- the pattern or mechanism;
- independent verification steps;
- questions the user can ask.

The validator rejects person-level conclusions, `safe`/`scam`/`fraud confirmed`, numerical risk
scores, fabricated contacts, claimed external checks, leaked internal IDs, unsupported links, and
missing authoritative rule coverage.

Each red flag is an `Evidence` object carrying the bullet text and a `source_id` naming the
detected rule, signal kind, or selected card it rests on. A bullet whose `source_id` is outside
that evidence set is dropped rather than rejecting the draft; a draft in which no bullet cites
anything keeps its flags and records `grounding_unsupported`, so a provider that ignores the
nested schema degrades visibly instead of emptying every answer. `verify` and `ask` carry no
provenance — generic verification advice is acceptable, a generic accusation is not. Bullets that
are nothing but a stock safety phrase are dropped by the same per-bullet pass. Governed by
[PIPELINE_V2.md](PIPELINE_V2.md) §3 and §5; enabled by `ANSWER_GROUNDING_ENABLED`.

### Statuses

The engine uses categorical statuses such as `ok`, `no_signal`, `empty_input`, `meta`, `off_topic`,
`low_ocr`, `rate_limited`, `timeout`, `llm_error`, `ocr_error`, `unsupported_media`, and
`safety_fallback`.
`meta` is a deterministic, non-billable short-circuit for chatter about the bot itself (greetings,
"what can you do", thanks) that never reaches the rule pack or the LLM — see `app.engine.meta`.
`off_topic` covers the open-ended non-situations no phrase list can enumerate ("what day is it").
The model classifies these via the `situation_type` field on `DraftOutput`, and the reply is fixed
localized copy — none of the model's prose is rendered, so that path needs no safety validation.
Two guards keep it from swallowing a real case: `checkable` is the default when the field is absent,
and any deterministic rule hit overrides an `off_topic` classification. It is billable, because it
costs a real model call and the daily limit is what caps junk volume.
Error classes are categorical identifiers, never exception messages.

## 5. Rules and payment protection

`rules/families.yaml` is the sole active rule pack. Stable `fs.*` rule IDs must not be
renamed because events, knowledge cards, tests, and sanitized Share summaries reference them.

A rule may carry three optional precision controls ([PIPELINE_V2.md](PIPELINE_V2.md) §6):
`exclude` patterns that suppress it whatever else matched, `match_mode: word_prefix` for Uzbek
agglutination, and a `requires` co-occurrence gate. All three are optional, default to the
historical behavior, and are editable at `/admin/rules`. A gated rule may only reference rules
that carry no gate of their own, which is validated at load time.
`tools/eval_rules.py` scores the pack against `tests/fixtures/eval/corpus.json` and fails when the
false-positive rate on the benign half exceeds its threshold.

The pack covers credential theft, urgency/secrecy, authority impersonation, upfront payment,
verification avoidance, implausible promises, suspicious links/QR codes, incoming-payment receipt
inconsistency, screenshot claims, overpayment/refund requests, and pressure to release goods.

A screenshot, receipt, or message never proves that an incoming payment arrived. Relevant output
must tell the user to verify the matching transfer independently in the receiving bank/payment
account before refunding money or releasing goods.

### Operator overrides

The repository is public, so shipped keyword lists and cards are readable by the people they
describe. New pattern and card work therefore lives in the `rule_override` and
`knowledge_card_override` tables (`app/rules_store/`, `app/knowledge_store/`), each on its own
declarative base beside `EditorialBase` — operator-authored reference data, never user content, and
so outside the zero-content contract enforced over `app.data.models.Base`.

Both merge onto their shipped YAML baseline **by ID**: a matching ID replaces, a new ID adds, and a
`disabled` rule row or a `draft`/`retired` card row suppresses the baseline entry. Wholesale
replacement was rejected because it would force re-entering an entire pack before adding one entry.

`load_rule_pack()` and `KnowledgeStore.load()` keep their synchronous signatures and are served from
process-level snapshots refreshed every `RULE_PACK_REFRESH_MINUTES` / `KNOWLEDGE_REFRESH_MINUTES`.
Both failure paths are fail-safe: an unreachable database leaves the previously published pack in
force and ultimately falls back to the shipped YAML, and a single malformed row is skipped. Falling
back to an *empty* knowledge base is specifically not acceptable — `retrieval_status` would read
`empty` rather than `unavailable`, hiding the degradation.

Patterns are validated on write (regexes must compile, literals must clear a minimum length). When a
card override contributes, `kb_version` becomes `<base-version>.db<YYYYMMDDHHMMSS>`, constrained by
`VERSION_RE` in `app/data/repo.py`, which rejects a bad `kb_version` on every `check_event` write.

Operators edit both through `/admin/rules` and `/admin/cards`, which reuse the existing
`ADMIN_ACCESS_KEY` surface. Each screen carries a dry-run that drives the *real* matcher and the
*real* retrieval path, so a preview cannot drift from production.

Moving this work out of git does not retract what is already published; it only keeps future work
unpublished.

## 6. Knowledge and model boundary

Only approved, versioned cards from `knowledge/cards/` may be retrieved. Cards explain
patterns and verification steps; they are not official-source evidence and cannot establish
identity, intent, or fraud.

A card may carry a `localized` block of reviewer-approved wording per reply language. When such a
card is selected by a rule or signal trigger — never by an alias cue or the router — its bullets
are composed into the answer verbatim and the model only supplies the `pattern` sentence and any
warning sign the cards miss ([PIPELINE_V2.md](PIPELINE_V2.md) §4). Composition happens before
validation: a card is reviewed, not trusted. A card with no wording for the reply language falls
back to model localization.

The semantic router is optional and receives the strict minimized text plus a server-generated
allowlist; it never receives submitted names or raw URLs. It may select only allowed card IDs.
Empty or unavailable knowledge must degrade safely to the rule and signal context.

The full knowledge contract lives in
[AI_KNOWLEDGE_PIPELINE.md](AI_KNOWLEDGE_PIPELINE.md).

## 7. Persistence and privacy

Active tables contain consent, check-event metadata, categorical feedback, rate limits, and
deletion audit rows. `user_key` is derived with HMAC; raw Telegram IDs are not stored or logged.

Founder-authored public cases live in the separate `editorial_post` table and
`app.content.models.EditorialBase`. Every record contains two deliberately authored language
versions plus draft/publication metadata and may contain one normalized WebP cover with bilingual
alt text. No user key or submitted check content enters this table, and editorial rows are not part
of `/delete_my_data` because they are operator-owned public content.

The `story_submission` table of the retired story-capture flow was dropped by migration
`0013_drop_story_submission` under founder authorization. It held `minimized_text`, the last
text column in the schema; no table now has a column that can hold submitted content, and
`tests/test_schema_privacy.py` enforces that with an empty allowlist.

`log_event()` and `log_error()` accept only allowlisted categorical metadata. Submitted content,
decoded QR payloads, OCR text, model output, URLs, contacts, and exception strings are forbidden.
Each web request, Telegram update, or direct checker call receives a server-generated random
`request_id` so its start, error, and completion records can be connected without identifying the
user.

## 8. Channel behavior

### Telegram

`/start` selects language and presents the current privacy notice. Content is processed only after
the current notice version is accepted. The bot returns the formatted result, check-bound
categorical feedback buttons, and a sanitized Share action. `/privacy` and `/delete_my_data` remain
available.

### Web

`GET /` and `GET /check` render the same anonymous checker. `POST /check` always builds the active
check input. Uploads are size/pixel limited, kept ephemeral, same-origin protected, and image
checks require Turnstile when configured. Session and IP-derived keys are pseudonymous.

`GET /cases` and `GET /cases/{slug}` expose published editorial cases only. `/admin` is disabled
unless `ADMIN_ACCESS_KEY` is configured. When enabled, a short-lived signed HttpOnly cookie protects
the founder dashboard and bilingual editor; same-origin checks cover every admin write. Drafts are
never returned by public routes. Founder cover uploads are size/dimension bounded, metadata-stripped,
and re-encoded before persistence. Post bodies are rendered as escaped plain text, not trusted HTML.

`/merchants` is only a `308` compatibility redirect to `/check`. `/scams` and `/sitemap.xml` are not
product routes. `/healthz` checks process liveness; `/readyz` also checks database connectivity.

## 9. Observability and operator tools

Operational metrics and feedback-label reports read `check_event` rows. They expose
aggregate counts, statuses, languages, cost/latency, no-signal rate, safety fallback counts,
knowledge coverage, and categorical feedback without user keys or check IDs.

Runtime event and error records remain local in Docker's rotated logs. Search by the anonymous
`request_id` returned in web response headers or included in operator alerts; never add request
bodies, exception strings, submitted content, IP addresses, or raw platform identifiers.

Supported tools include:

```bash
python -m app.tools.metrics
python -m app.tools.metrics --days 30
python -m app.tools.metrics labels --since 2026-07-01
python -m app.tools.knowledge_gaps --days 7
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
- all user-facing copy exists in both reply languages (`uz_latn`, `ru`);
- no active path persists or logs submitted content;
- outputs remain non-verdict, grounded, and independently verifiable;
- the deployed rules/knowledge assets load successfully;
- consent, deletion, retention, rate limits, Share, feedback, and readiness checks remain green.
