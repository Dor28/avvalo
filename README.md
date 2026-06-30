# Avvalo

Avvalo is an AI safety assistant for Uzbekistan. Version 1 uses one shared checking
engine for Family Shield and Seller Guard, exposed through Telegram and an anonymous web
application.

**Live bot:** [@Avvalo_official_bot](https://t.me/Avvalo_official_bot) — the official Avvalo bot on Telegram.

## T1 development boot

Requirements: Docker with Compose, or Python 3.11+ with PostgreSQL 16.

```bash
docker compose up --build
```

The `app` service currently performs the T1 database connectivity check and then remains
running. Telegram, engine, and web behavior are added in later numbered build tasks.

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
