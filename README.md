# Avvalo

Avvalo is a privacy-first AI safety assistant for Uzbekistan. It helps people
check suspicious messages, screenshots, payment claims, links, and deals before
they reply, send money, share personal details, or act on a claim.

The product rule is simple:

> Verify the situation, document, or process. Never rate the reputation of a
> person.

Avvalo is Telegram-first, works in Uzbek Latin, Uzbek Cyrillic, and Russian, and
is built around one shared checking engine used by multiple faces:

- **Avvalo consumer checker**: checks suspicious messages and returns risk
  signs, verification steps, and questions to ask before the user acts.
- **Avvalo Merchants**: seller-side checks for payment screenshots, order chats,
  courier/refund pressure, and "verify in your real bank app" workflows.
- **Anonymous web channel**: a thin server-rendered surface over the same engine,
  with Turnstile-gated image uploads and session/IP limits.

Live Telegram bot: [@Avvalo_official_bot](https://t.me/Avvalo_official_bot)

## Status

The v1 codebase contains the production-shaped checker: Telegram bot, anonymous
web app, rule packs, OCR providers, OpenAI-compatible LLM adapter, safety
validator, consent/deletion flows, privacy-safe metrics, Docker deployment, and
tests.

The current product direction is **Check, Learn, Share**:

1. **Check** suspicious content through the bot or web app.
2. **Learn** from public scam-library and education content.
3. **Share** opt-in, reviewed, de-identified stories later.

See [docs/ROADMAP.md](docs/ROADMAP.md) for the current launch-phase tasks. The
first step there is production smoke verification before adding the next growth
features.

## What Avvalo Returns

Every successful check returns a fixed, non-verdict structure:

- Red flags found in the submitted situation.
- What the user should verify independently.
- Questions to ask before paying, replying, or sending information.
- A limitation line making clear Avvalo did not certify safety and did not judge
  a person.

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
      rules on local raw text
              |
      PII minimization
              |
 OpenAI-compatible LLM call
              |
 deterministic safety validator
              |
 formatted UZ/RU response
              |
 privacy-safe event metadata only
```

Important design choices:

- The rule engine runs locally on raw text before minimization.
- The LLM receives minimized text plus structured rule signals, not raw contact
  details.
- Submitted text, OCR text, images, captions, model prompts, and model outputs
  are not stored in the database.
- PostgreSQL stores consent, check metadata, feedback, rate limits, deletion
  logs, cost, latency, status, and rule IDs only.
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
rules/          YAML rule packs for family and merchant faces
prompts/        safety and face-specific prompt templates
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
`http://localhost:8000/check` for the consumer checker. The merchant checker
remains available by direct URL at `http://localhost:8000/merchants`, but is not
linked from the public navigation.

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
| `DAILY_LIMIT_FAMILY` | Daily Telegram checks for family face. |
| `DAILY_LIMIT_MERCHANTS` | Daily Telegram checks for merchant face. |
| `OPERATOR_ALERT_CHAT_ID` | Founder chat for minimized story review and debounced technical alerts. |
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

Follow [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) end to end. The production
guide includes server hardening, `.env` handling, GHCR login, TLS bootstrap,
backups, scaling notes, and a go-live checklist.

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

- Do not store submitted content unless a future task explicitly creates a
  consented, minimized, reviewed story-capture exception.
- Do not add person, phone, card, or "reported N times" lookup features.
- Do not weaken the safety prompts, validator, or output contract casually.
- Do not put analysis logic in Telegram handlers or web routes; call the shared
  engine.
- Keep the LLM API key backend-only.
- Run privacy/schema tests when touching persistence.
- Extend rule packs and prompts carefully; they are safety-critical product
  assets.

## Key Documentation

Start here:

- [docs/ROADMAP.md](docs/ROADMAP.md) - current launch-phase work and next tasks.
- [docs/PRODUCT_VISION.md](docs/PRODUCT_VISION.md) - Check, Learn, Share vision.
- [docs/PRODUCT_GUIDE.md](docs/PRODUCT_GUIDE.md) - authoritative product and
  safety direction.
- [docs/V1_TECHNICAL_PLAN.md](docs/V1_TECHNICAL_PLAN.md) - executable
  architecture and engineering contract.
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) - production deployment guide.
- [docs/V1_CURRENT_PM_REVIEW.md](docs/V1_CURRENT_PM_REVIEW.md) - current product
  risks and backlog.
- [docs/PRODUCT_HORIZONS.md](docs/PRODUCT_HORIZONS.md) - future option map.

For the full docs index, see [docs/README.md](docs/README.md).

## License

See [LICENSE](LICENSE).
