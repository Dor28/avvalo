# Avvalo

Avvalo is a privacy-first safety assistant for Uzbekistan. It helps people check
suspicious messages, screenshots, links, QR codes, payment requests, offers, and
documents before they reply, pay, install, sign, or share personal information.

The product rule is simple:

> Verify the situation, artifact, process, or source. Never rate the reputation
> of a person.

Avvalo is one consumer product, Telegram-first, and available in Uzbek (Latin
script) and Russian. Cyrillic-Uzbek input is still read and analysed, but
replies are always Latin-script Uzbek. Telegram and the anonymous web checker
are two channels over one shared engine.

The product loop is:

> **Send → Understand → Verify → Act → Share**

Live Telegram bot: [@Avvalo_official_bot](https://t.me/Avvalo_official_bot)

## Status

The v1 codebase contains the explanation baseline: Telegram bot, anonymous web
app, rule packs, OCR providers, an OpenAI-compatible LLM adapter, reviewed
knowledge retrieval, a safety validator, consent/deletion flows, privacy-safe
metrics, Docker deployment, and tests.

The runtime has one active product face, internally named `family`. Seller,
payment-screenshot, courier, and refund situations are handled by the same
checker and its safety rules. Avvalo Merchants, the public scam library, story
capture, and Scam Pulse are retired surfaces, not optional product modes.

The next product capability is **Avvalo Verify**: bounded, source-backed facts
for official identity, links/QR codes, and regulated-organization/license
routing. It is not considered built or live yet. The manual validation gate in
[docs/VERIFY_VALIDATION.md](docs/VERIFY_VALIDATION.md) comes before feature code.

## What Avvalo Returns

Every successful baseline check returns a fixed, non-verdict structure:

- Red flags found in the submitted situation.
- What the user should verify independently.
- Questions to ask before paying, replying, or sending information.
- A limitation line making clear Avvalo did not certify safety and did not judge
  a person.

After Avvalo Verify passes validation and is implemented, a result may also
include up to three typed source facts, each with a named source, observation
time, and explicit limitation. Source failure stays `unavailable`; absence from
one source never becomes a verdict.

The system must never say "safe", "scammer", "fraud confirmed", or provide a
person-level accusation.

## Architecture

```text
Telegram bot            Anonymous web app
    |                         |
    +---- same CheckInput ----+
              |
              v
        shared engine
              |
      OCR when image input
              |
      rules/signals on local raw text
              |
      PII minimization
              |
 reviewed knowledge retrieval
              |
 OpenAI-compatible answer LLM
              |
 deterministic safety validator
              |
 formatted UZ/RU response
              |
 privacy-safe event metadata only
```

Important design choices:

- The rule engine runs locally on raw text before minimization.
- Rules are authoritative facts, not a gate: a zero-rule message still reaches
  semantic analysis.
- The LLM input is minimized text plus structured rule facts/signals and
  zero to three backend-selected, reviewed knowledge cards/cases — never raw
  contact details or unrestricted database access.
- A retrieved case is guidance, not proof about the current situation or person.
- Submitted text, OCR text, images, captions, model prompts, and model outputs
  are not stored in the database.
- PostgreSQL stores consent, check metadata, feedback, rate limits, deletion
  logs, cost, latency, statuses, rule/knowledge IDs, component versions, and
  public-feed domain hashes only.
- Web and Telegram both call `app.engine.pipeline.run_check()`; no analysis
  logic lives in the client/channel layer.

## Repository Layout

```text
app/
  bot/          Telegram onboarding, consent, checks, feedback, deletion
  web/          FastAPI routes, Jinja templates, anonymous sessions, abuse gates
  engine/       OCR, rules, minimization, LLM, validation, formatting pipeline
  data/         SQLAlchemy models, repo helpers, Alembic-backed persistence
  obs/          privacy-safe events, metrics, cost accounting
  privacy/      consent and pseudonymous user-key helpers
  tools/        operator CLI modules
rules/          YAML rules for the single Avvalo checker
knowledge/      versioned knowledge cards and reviewed case references
prompts/        shared safety instructions and the Avvalo task template
tests/          unit/integration tests and golden fixtures
tools/          standalone operator/research tools, including model eval
deploy/         production env template, nginx, backup/restore helpers
docs/           product, technical, deployment, and roadmap documents
```

## Requirements

- Python 3.11+
- Docker with Compose
- PostgreSQL 16 when running outside Compose
- Optional for local LLM development: Ollama with `qwen2.5:7b-instruct`
- Optional for image/OCR checks: Google Cloud Vision credentials, Tesseract, or
  PaddleOCR depending on `OCR_PROVIDER`

## Quick Start with Docker

The fastest boot is Docker Compose. It starts PostgreSQL and the app container.
Without a real Telegram token and with `WEB_ENABLED=false`, the app validates
configuration, connects to the database, and idles.

```bash
docker compose up --build
```

Run the connectivity check inside the app container:

```bash
docker compose exec app python -m app.main --check
```

### Enable the Web App Locally

Create a local env file and turn on the web channel:

```bash
cp .env.example .env
```

Set at least:

```env
WEB_ENABLED=true
WEB_PORT=8000
WEB_SESSION_SECRET=development-only-web-secret-change-me
APP_HMAC_SECRET=development-only-hmac-secret-change-me
```

Then boot:

```bash
docker compose up --build
```

Open `http://localhost:8000` for the public landing page and
`http://localhost:8000/check` for Avvalo. There is no separate merchant or
content-library product surface.

Text checks require a reachable LLM endpoint. Image checks also require an OCR
provider and, on the web, Turnstile configuration unless tests/mocks bypass it.

### Optional Local LLM

The compose file includes an optional Ollama service:

```bash
docker compose --profile local-llm up -d ollama
docker compose exec ollama ollama pull qwen2.5:7b-instruct
docker compose --profile local-llm up --build
```

With the default compose settings, the app reaches Ollama at
`http://ollama:11434/v1`.

## Local Python Development

Install the package and dev dependencies:

```bash
python -m pip install -e ".[dev]"
```

Start only PostgreSQL with Docker:

```bash
docker compose up -d db
```

Copy `.env.example` to `.env`, then set `DATABASE_URL` for local host access:

```env
DATABASE_URL=postgresql+asyncpg://avvalo:avvalo@localhost:5432/avvalo
```

Apply migrations:

```bash
alembic upgrade head
```

Run a config/database check:

```bash
python -m app.main --check
```

Run the service:

```bash
python -m app.main
```

## Test and Quality Commands

```bash
pytest
ruff check
python tools/secret_scan.py --all
```

Useful focused checks:

```bash
pytest tests/test_schema_privacy.py
pytest tests/test_engine_pipeline.py
pytest tests/test_t13_web.py
python -m app.tools.metrics --json
```

Run the model-selection benchmark before changing hosted models:

```bash
python tools/eval_models.py
```

The eval scores mechanical safety/format behavior and writes outputs under
`eval_out/`; Uzbek quality still needs manual review.

## Configuration

Runtime config is loaded from environment variables through
[`app/config.py`](app/config.py). Important variables:

| Variable | Purpose |
|---|---|
| `TELEGRAM_TOKEN` | Telegram bot token. Placeholder disables polling in dev. |
| `DATABASE_URL` | Async SQLAlchemy PostgreSQL URL. |
| `APP_HMAC_SECRET` | Stable secret for pseudonymous Telegram user keys. |
| `WEB_SESSION_SECRET` | Stable secret for anonymous web sessions. |
| `LLM_BASE_URL` | OpenAI-compatible endpoint, for example OpenRouter or Ollama. |
| `LLM_API_KEY` | LLM provider API key. Keep backend-only. |
| `LLM_MODEL` | Model ID selected by eval. |
| `OCR_PROVIDER` | `gcv`, `tesseract`, `paddleocr`, or local stub paths. |
| `GOOGLE_APPLICATION_CREDENTIALS` | Cloud Vision service-account path when using GCV. |
| `NOTICE_VERSION` | Consent notice version; bump to force re-consent. |
| `DAILY_LIMIT_FAMILY` | Daily Telegram checks for the Avvalo checker. |
| `OPERATOR_ALERT_CHAT_ID` | Founder chat for debounced technical alerts. |
| `OPERATOR_ALERT_DEBOUNCE_S` | Minimum interval between duplicate technical alerts. |
| `SENTRY_DSN` | Optional Sentry DSN; blank disables external error tracking. |
| `SENTRY_ENVIRONMENT` | Environment tag for privacy-safe Sentry error events. |
| `WEB_ENABLED` | Starts the FastAPI web app in the shared process. |
| `TURNSTILE_SITE_KEY` / `TURNSTILE_SECRET` | Gates web image uploads. |
| `WEB_COOKIE_SECURE` | Must be `true` behind HTTPS in production. |

Use `.env.example` for local development and
[`deploy/env.prod.example`](deploy/env.prod.example) for production.

## Production Deployment

Production is a single-VM Docker Compose deployment targeting Hetzner:

- `docker-compose.prod.yml` runs app, PostgreSQL, nginx, and certbot.
- `deploy/nginx/` contains the TLS/reverse-proxy template and bootstrap helper.
- `deploy/backup.sh` and `deploy/restore.sh` cover database backup/restore.
- GitHub Actions can test, build, push to GHCR, and deploy on `main`.

Start from [`deploy/env.prod.example`](deploy/env.prod.example), validate
`docker-compose.prod.yml`, bootstrap TLS with `deploy/nginx/init-letsencrypt.sh`,
and use the scripts under `deploy/` for update, backup, and restore operations.

Secrets must live only in the server `.env`, GitHub Secrets, and provider
dashboards. Never commit real `.env` values, API keys, Telegram tokens, OCR
credentials, screenshots of secrets, or provider keys.

The repo includes a local pre-commit secret scanner:

```bash
git config --get core.hooksPath
python tools/secret_scan.py --all
```

`core.hooksPath` should be `.githooks`, so commits run
`tools/secret_scan.py --staged`.

## Engineering Guardrails

- Do not store submitted content. `story_submission.minimized_text` is a legacy
  stewardship-only exception: no new writes or product reads; old rows remain
  covered by `/delete_my_data` and retention until a separately authorized purge.
- Keep one active face (`family`). Merchant payment protections belong in the
  main checker; do not recreate Merchants, scam-library, story-capture, or
  Scam-Pulse surfaces.
- Do not add person, phone, card, or "reported N times" lookup features.
- Do not weaken the safety prompts, validator, or output contract casually.
- Do not put analysis logic in Telegram handlers or web routes; call the shared
  engine.
- Keep the LLM API key backend-only.
- Run privacy/schema tests when touching persistence.
- Extend rule packs and prompts carefully; they are safety-critical product
  assets.

## Key Documentation

Read in this order:

- [docs/PRODUCT_GUIDE.md](docs/PRODUCT_GUIDE.md) — canonical product and safety.
- [docs/ROADMAP.md](docs/ROADMAP.md) — the only active order of work.
- [docs/VERIFY_VALIDATION.md](docs/VERIFY_VALIDATION.md) — experiment and gates.
- [docs/V1_TECHNICAL_PLAN.md](docs/V1_TECHNICAL_PLAN.md) — current implemented
  architecture and engineering constraints.
- [docs/AI_KNOWLEDGE_PIPELINE.md](docs/AI_KNOWLEDGE_PIPELINE.md) — explanation
  knowledge and LLM safety contract.

For the full docs index, see [docs/README.md](docs/README.md).

## License

See [LICENSE](LICENSE).
