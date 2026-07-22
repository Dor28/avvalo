# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Avvalo — a "check before you commit" assistant for Uzbekistan. Users send a suspicious message, screenshot, link, QR code, payment request, offer, or document (Uzbek Latin/Cyrillic or Russian) through Telegram or an anonymous web page. One shared engine explains red flags and next actions. The next product capability, Avvalo Verify, may add typed source facts only after the validation gate in `docs/VERIFY_VALIDATION.md`. Two rules shape the whole codebase: verify the **situation, never the person**, and never issue "safe"/"scam" **verdicts**.

## Commands

```bash
pip install -e ".[dev]"                 # Python 3.11+
pytest -q                               # full suite — no services needed (in-memory SQLite)
pytest tests/test_engine_pipeline.py -q # one file
pytest -q -k "name_substring"           # one test
ruff check .                            # lint: py311, line length 100, E/F/I/UP/B/SIM/RUF

docker compose up --build               # full local stack: Postgres 16 + migrations + app
docker compose --profile local-llm up -d ollama   # optional offline LLM
python -m app.main --check              # one-shot config + DB connectivity check
alembic upgrade head                    # apply migrations (compose does this on boot)
```

**Pushing to `main` deploys to production.** `.github/workflows/deploy.yml` gates on `pytest` only (ruff is non-blocking), builds an image to GHCR, and deploys it to the Hetzner VM on every push to `main`. Work on a branch unless the change should ship.

All configuration comes from environment variables via [app/config.py](app/config.py) (pydantic-settings, reads `.env`); [.env.example](.env.example) documents every knob. Never hardcode a tunable — add it to `Settings` and `.env.example`.

## Architecture

One process ([app/main.py](app/main.py)) runs everything: the aiogram Telegram bot (polling), the FastAPI anonymous web channel (when `WEB_ENABLED=true`), and the retention scheduler, sharing one async SQLAlchemy engine.

**One public product, one checker — and no product-face concept.** There is a single consumer
checker with a single rule pack (`rules/`), prompt (`prompts/check.txt`), and daily limit
(`DAILY_CHECK_LIMIT`). Seller, payment-screenshot, courier, and refund situations all use it.
The former `merchants` face, scam library, story-capture flow, and Scam Pulse are retired and must
not be restored from git history.

The `face` discriminator that used to select between products is **gone** — from the code and from
the database (migration `0006_drop_face`). Do not reintroduce it, and do not add a "mode" or
"product" parameter in its place. Two names survive and mean something different:

- `RuleHit.family` / `rules/families.yaml` — the **scam-family taxonomy** (`credential_theft`,
  `urgency_secrecy`, …). Nothing to do with products.
- `fs.` / `sg.` rule-ID prefixes and `family.*` knowledge-card IDs — frozen opaque identifiers kept
  stable because they are persisted in `check_event.rule_ids` / `knowledge_card_ids` and matched by
  the leak filter in `validate.py`. Never renamed; never parsed for meaning.

Channels (`app/bot/`, `app/web/`) are thin adapters that build a `CheckInput` and call
`run_check()` — new product behavior belongs in the engine, not in a channel handler.

**The pipeline** ([app/engine/pipeline.py](app/engine/pipeline.py), `run_check`) is the core; every check from every channel flows through the same stages:

1. Rate limit per (user, day); statuses that never reached the model refund the slot. The web
   channel's per-IP guard shares `rate_limit` under `scope="web_ip"`.
2. Content: text as-is, or image → OCR provider with a confidence gate (`low_ocr` below threshold).
3. Language resolution — the reply language follows the content, not the UI.
4. Deterministic rules (`app/engine/rules/`): keyword packs in `rules/*.yaml` (per-script keyword groups, matched on raw text) plus regex extractors → `RuleHit`s and `Signal`s. `rules/shared/` holds URL-reputation feed data and is deliberately *not* loaded as a rule pack.
5. `minimize()` strips PII before anything is sent to the LLM.
6. LLM call in JSON-schema mode via an OpenAI-compatible provider; prompt = `prompts/system_safety.txt` + `prompts/check.txt` with rule hits injected as grounded facts.
7. Deterministic safety validator ([app/engine/validate.py](app/engine/validate.py)): bans verdict words in ru/uz_latn/uz_cyrl/English, strips contacts/links/card numbers/OTPs, caps list lengths; one corrective retry, then `safety_fallback`.
8. `format_result` renders the reply in the resolved language.

Boundary contracts are Pydantic models in [app/engine/types.py](app/engine/types.py) (`CheckInput`, `CheckResult`, `CheckStatus`, `DraftOutput`); extend those instead of passing loose dicts. New statuses must also be added to the allow-set in [app/data/repo.py](app/data/repo.py).

**Providers are injectable and env-selected.** LLM = any OpenAI-compatible host (`LLM_BASE_URL`/`LLM_MODEL`; OpenRouter Qwen in prod, Ollama locally). OCR = `OCR_PROVIDER` ∈ gcv | tesseract | paddleocr | local_stub behind `app/engine/ocr/base.py`. Tests pass fake providers directly into `run_check(..., llm_provider=, ocr_provider=)` — keep new external dependencies injectable the same way.

**Data layer:** async SQLAlchemy + asyncpg on PostgreSQL 16; Alembic owns the schema. Functions in `app/data/repo.py` take a caller-provided `AsyncSession` and flush; the caller owns commit/rollback. Unit tests run on in-memory aiosqlite (see `RULE_IDS_TYPE` variant pattern in models.py for Postgres-only column types).

## Privacy invariants (do not weaken)

The legal posture depends on these; several are enforced by tests that will fail the build:

- **Submitted content is never persisted or logged.** `raw_text` / `image_bytes` / `caption` on `CheckInput` are ephemeral. `check_event` rows and `log_event()` output carry only IDs, enums, rule IDs, and metrics.
- **Active product writes have no content columns.** `tests/test_schema_privacy.py` rejects new
  content-like persistence. The existing `story_submission.minimized_text` column is legacy
  stewardship only: no new writes or product reads, while `/delete_my_data` and retention continue
  to cover old rows until a separately authorized purge removes the table.
- **`CheckInput` carries no product discriminator.** `tests/test_types_contract.py` asserts `face`
  stays absent, so the retired concept can't creep back through the boundary type.
- **Users are pseudonymous:** `user_key = HMAC_SHA256(APP_HMAC_SECRET, telegram_id)[:32]` ([app/privacy/user_key.py](app/privacy/user_key.py)); raw Telegram IDs are never stored or logged.
- Retention ([app/data/retention.py](app/data/retention.py)) prunes aged rows; `/delete_my_data` is audited in `deletion_log`.
- `tests/test_secret_scan.py` scans the tree for committed secrets.

## Conventions

- **Spec-driven:** [docs/PRODUCT_GUIDE.md](docs/PRODUCT_GUIDE.md) defines product scope;
  [docs/ROADMAP.md](docs/ROADMAP.md) is the only current work queue;
  [docs/V1_TECHNICAL_PLAN.md](docs/V1_TECHNICAL_PLAN.md) describes the retained core and clearly
  marks removed legacy surfaces as history. Module docstrings cite technical-plan sections
  (§5.1, §9, …) — keep those references in sync.
- Tests named `test_tNN_*.py` map to the numbered build history in V1_TECHNICAL_PLAN §13; the
  active golden end-to-end fixtures live in `tests/fixtures/golden/checks.json`.
- **Every user-facing string exists in all three languages** (`uz_latn`, `uz_cyrl`, `ru`): `app/bot/texts.py`, `app/web/routes.py`, `app/engine/format.py`. These files carry E501/RUF001 lint exemptions for long lines and Cyrillic lookalike glyphs — don't "fix" those.
- Async end-to-end; pytest runs with `asyncio_mode = "auto"` (no `@pytest.mark.asyncio` needed).
- Style follows ruff config in [pyproject.toml](pyproject.toml): 100-char lines, import sorting (I), modern syntax (UP). Module docstrings state purpose and spec section; internal helpers use frozen dataclasses, boundary types use Pydantic.
- `.claude/worktrees/` can hold stale checkouts with pre-rename names (family_shield/seller_guard, and the retired `face` plumbing) — exclude it when searching the repo.
