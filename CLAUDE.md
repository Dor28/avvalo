# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Avvalo — a digital-safety assistant for Uzbekistan, built around one promise: **it never tells you something is safe; it makes you hard to deceive.** Users send a suspicious link, QR code, message, screenshot, payment request, offer, or document (Uzbek Latin/Cyrillic or Russian) through Telegram or an anonymous web page, and one shared engine explains what deserves attention and what to do next.

The product runs at three tempos ([docs/PRODUCT_GUIDE.md](docs/PRODUCT_GUIDE.md) §4): a **Scanner** that answers a link or QR deterministically with no model call, a **Check** that analyses a full situation in chat, and **Knowledge** — founder-written explanations plus rare wave notifications. Avvalo Verify (typed facts from official registries) is **parked**, not next; see PRODUCT_GUIDE §9.

Three rules shape the whole codebase:

- verify the **situation, never the person**;
- never issue "safe"/"scam" **verdicts** — decisiveness goes into the recommended *action*, never into a claim about the object;
- never open a submitted destination, except through the one bounded exception in PRODUCT_GUIDE §8.1.

## Commands

```bash
pip install -e ".[dev]"                 # Python 3.11+
pytest -q                               # full suite — no services needed (in-memory SQLite)
pytest tests/test_engine_pipeline.py -q # one file
pytest -q -k "name_substring"           # one test
pytest -q --cov                         # + coverage; fails under the floor in pyproject.toml
ruff check .                            # lint: py311, line length 100, E/F/I/UP/B/SIM/RUF

# Run the same suite against real Postgres, as CI does. Only this exercises the
# shipped ARRAY(Text) columns; SQLite falls back to JSON (RULE_IDS_TYPE).
TEST_DATABASE_URL=postgresql+asyncpg://avvalo:avvalo@localhost:5432/avvalo pytest -q

docker compose up --build               # full local stack: Postgres 16 + migrations + app
docker compose --profile local-llm up -d ollama   # optional offline LLM
python -m app.main --check              # one-shot config + DB connectivity check
alembic upgrade head                    # apply migrations (compose does this on boot)
```

**Pushing to `main` deploys to production.** `.github/workflows/deploy.yml` runs two gating jobs — `test` (`ruff check .`, the `S`-rule security lint, and `pytest -q --cov` on SQLite) and `test-postgres` (Alembic `upgrade head`, a `downgrade base` + reapply round trip, then the suite against Postgres 16). Every step is blocking, so a lint failure or a coverage drop below the floor blocks the deploy. Only after both jobs pass does it build an image to GHCR and deploy it to the Hetzner VM. Work on a branch unless the change should ship.

All configuration comes from environment variables via [app/config.py](app/config.py) (pydantic-settings, reads `.env`); [.env.example](.env.example) documents every knob. Never hardcode a tunable — add it to `Settings` and `.env.example`.

## Architecture

One process ([app/main.py](app/main.py)) runs everything: the aiogram Telegram bot (polling), the FastAPI anonymous web channel (when `WEB_ENABLED=true`), and the retention scheduler, sharing one async SQLAlchemy engine.

**One public product, one checker — and no product-face concept.** There is a single consumer
checker with a single rule pack (`rules/`), prompt (`prompts/check.txt`), and daily limit
(`DAILY_CHECK_LIMIT`). Seller, payment-screenshot, courier, and refund situations all use it.
The former `merchants` face, scam library, story-capture flow, and Scam Pulse are retired and must
not be restored from git history. **Scam Pulse is not the same thing as the approved wave
notification** (ROADMAP Phase 3): that is a founder-authored push, two or three a month, never an
aggregate trend feed and never derived from user submissions.

The `face` discriminator that used to select between products is **gone** — from the code and from
the database (migration `0007_drop_face`). Do not reintroduce it, and do not add a "mode" or
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
4. Deterministic rules (`app/engine/rules/`): keyword packs in `rules/*.yaml` (per-script keyword groups, matched on raw text) plus regex extractors → `RuleHit`s and `Signal`s. `rules/shared/` holds reference data and is deliberately *not* loaded as a rule pack: the URL-reputation feed, and `official_domains.yaml` — the founder-reviewed catalog of impersonated organizations, shorteners, and public suffixes that [app/engine/url.py](app/engine/url.py) classifies against.
5. `minimize()` builds two ephemeral views: strict identifier minimization for knowledge
   retrieval/routing, and an answer-prompt view that retains submitted names and full URLs while
   still tokenizing phones, cards, credentials, codes, passports, addresses, and other protected
   values. Decoded QR payloads remain strictly minimized.
6. LLM call in JSON-schema mode via an OpenAI-compatible provider; only the answer model receives
   the name/URL-preserving view. The prompt is `prompts/system_safety.txt` + `prompts/check.txt`
   with rule hits injected as grounded facts.
7. Deterministic safety validator ([app/engine/validate.py](app/engine/validate.py)): bans verdict words in ru/uz_latn/Cyrillic-Uzbek/English, strips contacts/links/card numbers/OTPs, caps list lengths; one corrective retry, then `safety_fallback`.
8. `format_result` renders the reply in the resolved language.

**Two answer paths, one engine.** The pipeline above is the *Check* (long form). The *Scanner* short form — ROADMAP Phase 1, **not built yet** — resolves a submitted link or decoded QR through the same [app/engine/url.py](app/engine/url.py) analyzer and returns the three-state answer in PRODUCT_GUIDE §5.2 with **no LLM call**, without consuming `DAILY_CHECK_LIMIT`. Both forms pass the same validator. A scanner answer must never claim safety: its "nothing found" state reports the absence of a *finding*, which is not the absence of risk.

Boundary contracts are Pydantic models in [app/engine/types.py](app/engine/types.py) (`CheckInput`, `CheckResult`, `CheckStatus`, `DraftOutput`); extend those instead of passing loose dicts. New statuses must also be added to the allow-set in [app/data/repo.py](app/data/repo.py).

**Detection assets are database-backed with a YAML fallback.** The repo is public, so new keyword
and card work lives in `rule_override` / `knowledge_card_override` (`app/rules_store/`,
`app/knowledge_store/`) rather than in git; `rules/*.yaml` and `knowledge/cards/` are the shipped
fallback baseline. Overrides merge onto the baseline **by ID**, are served from process-level
snapshots so `load_rule_pack()` / `KnowledgeStore.load()` stay synchronous, and fail *safe* — an
unreachable database falls back to the shipped YAML, never to an empty pack. Operators edit them at
`/admin/rules` and `/admin/cards` (needs `ADMIN_ACCESS_KEY`), each with a dry-run that calls the real
matcher / real retrieval so a preview cannot drift from production.

**Providers are injectable and env-selected.** LLM = any OpenAI-compatible host (`LLM_BASE_URL`/`LLM_MODEL`; OpenRouter Qwen in prod, Ollama locally). OCR = `OCR_PROVIDER` ∈ rapidocr | gcv | tesseract | paddleocr | local_stub behind `app/engine/ocr/base.py`; `rapidocr` is the default and runs PP-OCRv5 locally on ONNX Runtime, with weights baked into the image at build time because the production container is read-only. `paddleocr` runs the same models through paddlepaddle and needs the `paddle` extra plus a writable model cache — it is kept only for accuracy comparisons. Providers are built once per process by `get_provider()` and warmed at boot from `app/main.py`; tests pass fake providers directly into `run_check(..., llm_provider=, ocr_provider=)` — keep new external dependencies injectable the same way.

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
- **Submitted destinations are never opened.** No code path fetches, renders, or executes a
  submitted URL or QR destination. The single bounded exception is shortener redirect resolution
  (PRODUCT_GUIDE §8.1): `HEAD` only, `https` and public addresses only, capped hops, no cookies,
  on an explicit user action, separate egress — and the resolved destination is shown once, never
  persisted, logged, or sent to a model. Widening this requires a founder decision recorded in the
  guide; do not let it drift into fetching page content.
- **Users are pseudonymous:** `user_key = HMAC_SHA256(APP_HMAC_SECRET, telegram_id)[:32]` ([app/privacy/user_key.py](app/privacy/user_key.py)); raw Telegram IDs are never stored or logged.
- Retention ([app/data/retention.py](app/data/retention.py)) prunes aged rows; `/delete_my_data` is audited in `deletion_log`.
- `tests/test_secret_scan.py` scans the tree for committed secrets.

## Conventions

- **Spec-driven:** [docs/PRODUCT_GUIDE.md](docs/PRODUCT_GUIDE.md) defines product scope;
  [docs/ROADMAP.md](docs/ROADMAP.md) is the only current work queue;
  [docs/V1_TECHNICAL_PLAN.md](docs/V1_TECHNICAL_PLAN.md) describes the retained core and clearly
  marks removed legacy surfaces as history. Module docstrings cite technical-plan sections
  (§5.1, §9, …) — keep those references in sync.
- Test modules are named for current behavior and product boundaries, not historical milestones;
  the active golden end-to-end fixtures live in `tests/fixtures/golden/checks.json`.
- **A golden fixture is executed, not just declared.** `tests/test_golden_e2e.py` runs every case
  through `run_check()`: `expected_rule_families` must fire, `expected_knowledge_card_ids` must be
  retrieved, and no `must_not_contain` phrase may reach the user in an `ok` reply — asserted by
  driving an adversarial model that tries to emit each one. `must_include` stays English
  reviewer-facing rationale (replies are `uz_latn`/`ru`, so it can never be a substring match);
  `expected_knowledge_card_ids` is its checkable form. Adding a case therefore buys reply-content
  cover, so add the hardest material from the content track (ROADMAP §6) here.
- **Every user-facing string exists in both languages** (`uz_latn`, `ru`): `app/bot/texts.py`, `app/web/routes.py`, `app/engine/format.py`. Uzbek replies are Latin-script only **today** — Cyrillic-Uzbek *output* is scheduled work (ROADMAP Phase 3), not a permanent boundary. Cyrillic-Uzbek *input* is already supported: `app/engine/language.py` detects it and resolves it to `uz_latn`, the `uz_cyrl` keyword groups in `rules/` and `knowledge/` still match it, and `app/engine/validate.py` still bans Cyrillic verdict words. These files carry E501/RUF001 lint exemptions for long lines and Cyrillic lookalike glyphs — don't "fix" those.
- Async end-to-end; pytest runs with `asyncio_mode = "auto"` (no `@pytest.mark.asyncio` needed).
- Style follows ruff config in [pyproject.toml](pyproject.toml): 100-char lines, import sorting (I), modern syntax (UP). Module docstrings state purpose and spec section; internal helpers use frozen dataclasses, boundary types use Pydantic.
- `.claude/worktrees/` can hold stale checkouts with pre-rename names (family_shield/seller_guard, and the retired `face` plumbing) — exclude it when searching the repo.
