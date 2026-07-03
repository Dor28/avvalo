# Avvalo

Avvalo is an AI safety assistant for Uzbekistan. Version 1 uses one shared checking
engine for the family/consumer side and Avvalo Merchants, exposed through Telegram and an
anonymous web application.

**Live bot:** [@Avvalo_official_bot](https://t.me/Avvalo_official_bot) — the official Avvalo bot on Telegram.

## Development boot

Requirements: Docker with Compose, or Python 3.11+ with PostgreSQL 16.

```bash
docker compose up --build
```

The local stack applies migrations, starts PostgreSQL, and boots the shared Avvalo
process. With real Telegram tokens it runs the configured bot face(s). With
`WEB_ENABLED=true` it also serves the anonymous web channel. Live LLM/OCR quality still
depends on configured provider credentials and should be smoke-tested before an alpha or
demo.

For a one-shot local connectivity check:

```bash
python -m app.main --check
```

## Production deployment

To deploy the MVP to a Hetzner VM (hardened Docker stack, TLS, scalable database,
backups), follow **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**. It uses
`docker-compose.prod.yml` and the configs under `deploy/`.

Submitted content must never be persisted or logged. See
`docs/V1_TECHNICAL_PLAN.md` and `docs/PRODUCT_GUIDE.md` before implementation work.
