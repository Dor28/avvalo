# Avvalo

Avvalo is an AI safety assistant for Uzbekistan. Version 1 uses one shared checking
engine for Family Shield and Seller Guard, exposed through Telegram and an anonymous web
application.

## T1 development boot

Requirements: Docker with Compose, or Python 3.11+ with PostgreSQL 16.

```bash
docker compose up --build
```

The `bot` service currently performs the T1 database connectivity check and then remains
running. Telegram, engine, and web behavior are added in later numbered build tasks.

For a one-shot local connectivity check:

```bash
python -m app.main --check
```

Submitted content must never be persisted or logged. See
`docs/V1_TECHNICAL_PLAN.md` and `docs/PRODUCT_GUIDE.md` before implementation work.

