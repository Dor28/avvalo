# Avvalo — v1 Technical Plan & Architecture (executable build spec)

> **Status:** Technical architecture · ready to implement · 2026-06-24
> **Audience:** The implementing engineer / coding model. **This document makes the decisions so you don't have to.** Where it says "MUST," do exactly that. Where it says "verify," check current external docs before coding (APIs change). Do not introduce new dependencies, services, or patterns not listed here without flagging it.
> **Implements:** [V1_BUILD_SCOPE.md](V1_BUILD_SCOPE.md) — one engine, two faces (Family Shield + Seller Guard). Safety/vision authority: [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md). Engine behaviour & golden examples: [FAMILY_SHIELD_VALIDATION.md](FAMILY_SHIELD_VALIDATION.md).

---

## 0. How to use this document

1. Read §1–§4 to understand the system, then build in the order of §13 (numbered tasks).
2. Each §13 task has **explicit acceptance criteria** — do not move on until they pass.
3. The contracts in §6–§9 are the source of truth for function signatures and data shapes. Match them exactly so modules compose.
4. **Golden rule:** submitted content (text, images, OCR text, model output) is *ephemeral* — it must **never** be written to a database, log, analytics event, or backup. If you are about to persist a string that came from the user, stop.
5. If a requirement here conflicts with [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md)'s safety rules, the guide wins — flag the conflict.
6. **Pre-authored assets already exist — use them, do not regenerate.** The safety-critical content was written by hand and reviewed: the three prompt files (`prompts/system_safety.txt`, `prompts/family_shield.txt`, `prompts/seller_guard.txt`), the trilingual rule packs (`rules/family_shield/families.yaml`, `rules/seller_guard/families.yaml`), the golden fixtures (`tests/fixtures/golden/family_shield.json` = 5 examples, `tests/fixtures/golden/seller_guard.json` = 3 examples), and the model eval (`tools/eval_models.py`). Wire the code to load these. You may *extend* rule keywords or fix bugs, but do not rewrite the prompts or weaken the safety wording without flagging it.

---

## 1. Locked technology stack

| Concern | Choice | Why (brief) | Notes |
|---|---|---|---|
| Language | **Python 3.11+** | Best AI/OCR ecosystem; most training data for the executor | Type-hint everything |
| Telegram | **aiogram 3.x** (async) | Modern, clean FSM, well-documented | Long-polling for dev; webhook optional later |
| Web API | **FastAPI** (async) | Runs in the same process; shares the engine + DB; pydantic-native; OpenAPI for free | Thin HTTP face over `run_check()` |
| Web UI | **Jinja2 templates + HTMX** + vanilla CSS | No SPA / Node build step; submit→swap-result; minimal for a solo build | Reuses the 3-language UI strings |
| Web abuse | **Cloudflare Turnstile** + IP/session rate-limit + upload caps | Open web has NO built-in anti-spam (unlike Telegram) — this is a v1 requirement | Captcha gates image upload |
| LLM | **Qwen (open weights)** via a neutral OpenAI-compatible host (OpenRouter / Together / Fireworks) | Chinese model with the broadest multilingual coverage → best odds on low-resource Uzbek; open weights ⇒ served off mainland China (US/EU/SG), so user data never enters China (key for a privacy product); OpenAI-compatible; cheap | Behind the provider interface (§8). Host + model set by env (`LLM_BASE_URL` / `LLM_MODEL`). Choose a host offering a **DPA + no-retention / no-training**. Confirm Uzbek quality with the eval (§8.1) before locking. **Self-hosting Qwen in-region is the production roadmap** (full data residency). |
| OCR | **Google Cloud Vision** `DOCUMENT_TEXT_DETECTION` | Strong Latin+Cyrillic; clear DPA | Behind an interface (§7). On-prem (Tesseract/PaddleOCR) is a later swap, stubbed now. |
| DB | **PostgreSQL 16** | Relational is enough (no graph DB); JSONB for event payloads; real TTL/backup story | SQLite allowed for *local unit tests only* |
| ORM / migrations | **SQLAlchemy 2.x + Alembic** | Standard | |
| Scheduler | **APScheduler** (in-process) | Daily TTL cleanup jobs | One process; fine for this scale |
| Config | **pydantic-settings** | Typed env config | |
| Rules | **YAML** files under `rules/` | Config-not-code (guide requirement) | Loaded at startup; hot-reload optional |
| Tests | **pytest** + **pytest-asyncio** | | Golden fixtures are mandatory |
| Lint/format | **ruff** | One tool | |
| Packaging | **uv** or **pip + pyproject.toml** | | |
| Deploy | **Docker + docker-compose** | One-command bring-up; UZ-region VPS for the residency story | services: `app` (bot+web), `db`; optional GPU `ollama` (`local-llm` profile) |

**Do not add:** a graph database, a message queue, Redis (use Postgres + in-process for this scale), a second LLM/OCR vendor, or a heavy SPA/Node frontend (the web client is server-rendered Jinja2 + HTMX — no build pipeline). Keep it boring.

### 1.1 Environment variables (`.env.example`)

| Var | Purpose |
|---|---|
| `TELEGRAM_TOKEN` | Bot token for the single Telegram channel |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@db:5432/avvalo` |
| `APP_HMAC_SECRET` | Secret for the pseudonymous user-key HMAC (rotate ⇒ keys change; keep stable) |
| `LLM_BASE_URL` | OpenAI-compatible endpoint of the chosen neutral host, e.g. `https://openrouter.ai/api/v1` (or Together / Fireworks) |
| `LLM_API_KEY` | Key for that host |
| `LLM_MODEL` | e.g. `qwen/qwen-2.5-72b-instruct` (verify exact id on the host; also try a current Qwen3 instruct in the eval) |
| `LLM_IN_RATE_PER_M` / `LLM_OUT_RATE_PER_M` | $/1M tokens for cost calc (from the host's pricing) |
| `OCR_PROVIDER` | `gcv` (production, Cloud Vision) or `tesseract` (offline dev — see §1.2) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to Cloud Vision service-account JSON (only when `OCR_PROVIDER=gcv`) |
| `OCR_MIN_CONFIDENCE` | default `0.5` |
| `NOTICE_VERSION` | consent notice version string; bump ⇒ re-consent |
| `DAILY_LIMIT_FAMILY_SHIELD` / `DAILY_LIMIT_SELLER_GUARD` | defaults 5 / 20 |
| `LLM_TIMEOUT_S` / `OCR_TIMEOUT_S` | latency guards (§14) |
| `MAX_OUTPUT_TOKENS` | default `600` |
| `OPERATOR_ALERT_CHAT_ID` | where to alert on a critical safety violation (§9) |
| `WEB_ENABLED` | `true` to serve the web app alongside the bot |
| `WEB_HOST` / `WEB_PORT` | uvicorn bind for FastAPI |
| `TURNSTILE_SITE_KEY` / `TURNSTILE_SECRET` | Cloudflare Turnstile (captcha) keys |
| `WEB_SESSION_SECRET` | signs the anonymous web session cookie (pseudonymous web key) |
| `WEB_DAILY_LIMIT` | anonymous checks per web session/IP per day (default 5) |

`config.py` loads these via pydantic-settings and fails fast if a required one is missing.

### 1.2 Local dev (Ollama, offline — no API keys)

You can build and integration-test the **entire pipeline with zero API keys, fully offline.** This is the recommended way to develop T1–T9 and T13. **Use it for plumbing, not for judging Uzbek quality** — a small local model writes rough Uzbek; that's the model size, not your code. Make the quality/model decision against hosted Qwen via the eval (§8.1).

**LLM via Ollama — two ways to run it.** The `openai_compat.py` adapter is host-agnostic, so "local" is just a different `LLM_BASE_URL`.

*Pattern A — containerized (recommended; this machine's Docker already has the `nvidia` runtime registered).* Ollama is an optional compose service behind a `local-llm` profile that shares the GPU (see the compose in T1); the app reaches it at `http://ollama:11434/v1`. Bring it up and pull the model once (the named volume keeps it):
```
docker compose --profile local-llm up -d ollama
docker compose exec ollama ollama pull qwen2.5:7b-instruct
```
*Pattern B — native Windows app (fallback if the container GPU misbehaves).*
```
winget install Ollama.Ollama          # then:  ollama pull qwen2.5:7b-instruct  &&  ollama serve
```
Containers then reach it at `http://host.docker.internal:11434/v1`.

Point the engine/eval at whichever you chose:
```
LLM_BASE_URL=http://ollama:11434/v1   # Pattern A · Pattern B: http://host.docker.internal:11434/v1 · bare host: http://localhost:11434/v1
LLM_API_KEY=ignored
LLM_MODEL=qwen2.5:7b-instruct
```
Reference dev hardware (RTX 4050, **6 GB VRAM / 16 GB RAM**): `qwen2.5:7b-instruct` runs fully on GPU (~25–40 tok/s) and is the daily driver. `qwen2.5:14b` runs with CPU offload (slow, ~5–10 tok/s) for an occasional Uzbek spot-check. **32B+ is not feasible on 6 GB / 16 GB — use the host for that.** Russian output looks reasonable at 7B; Uzbek looks rough — expected, not a bug.

*Verify GPU-in-container once:* `docker run --rm --gpus all ollama/ollama nvidia-smi` should list the RTX 4050.

*Production self-host (roadmap):* the same compose pattern runs on a Linux GPU server; for real throughput swap the `ollama/ollama` image for **`vllm/vllm-openai`** (also OpenAI-compatible) — only `LLM_BASE_URL` and the model name change, never `openai_compat.py`.

**OCR offline** — two ways to avoid a Cloud Vision key in dev:
- **Text-only path (simplest):** test forwarded/pasted-text checks; no OCR involved. Covers most of the pipeline.
- **Tesseract dev provider:** set `OCR_PROVIDER=tesseract` to use `engine/ocr/tesseract.py` (CPU, offline; install Tesseract + the `rus`, `uzb`, `uzb_cyrl` language data). Lower quality than Cloud Vision — a dev unblocker, not the production OCR. Production uses `OCR_PROVIDER=gcv`.

Postgres, the bot, and the web app already run locally via `docker compose`, so the full loop — bot/web → rules → minimize → local Qwen → validate → format — needs **no external account**.

---

## 2. System architecture

```
        ┌─────────── Telegram (aiogram) ───────────┐   ┌──── Web (FastAPI + HTMX) ────┐
        │ Family Shield face    Seller Guard face   │   │ anonymous check; Turnstile-  │
        │ (handlers, FSM, Telegram identity)        │   │ gated image upload           │
        └─────────────────────┬─────────────────────┘   └──────────────┬───────────────┘
                              │       same CheckInput → run_check()      │
                              ▼                                          ▼
        ┌───────────────────────────────────────────────────────────────────┐
        │                         CORE ENGINE (one pipeline)                  │
        │                                                                     │
        │  intake ─▶ OCR(if image) ─▶ rules(on RAW local text) ──┐           │
        │                                   │ emits RuleHit[] +   │           │
        │                                   │ structured signals  │           │
        │                                   ▼                     ▼           │
        │                          minimize(text) ─────▶ LLM(minimized text + │
        │                          (PII stripped,         rule hits + face +  │
        │                           signals kept)          language → JSON)   │
        │                                                       │             │
        │                                                       ▼             │
        │                                          safety validator ─▶ format │
        │                                                       │             │
        │   privacy-safe events + cost ◀── (no content) ────────┘             │
        └───────────────────────────────────────────────────────────────────┘
                                 │                          │
                                 ▼                          ▼
                       PostgreSQL (NO content)      Ephemeral workspace
                       consent / events /           (RAM + temp file,
                       feedback / limits            1-hour hard TTL, then deleted)
```

**Key ordering decision (resolves the review's privacy-vs-analysis tension):** the **rule engine runs on the RAW local text first** (it never leaves the server), extracts structured signals (links, phone "newness", card destination, etc.), *then* the text is minimized for the LLM. The LLM receives **minimized text + the structured signals as grounded facts.** This is why it can still explain "lookalike link" without the raw URL leaving in the prompt.

**The two faces share 100% of this pipeline.** A `Face` value (`family_shield` | `seller_guard`) selects (a) which rule pack loads and (b) which output template/prompt is used. Nothing else differs.

**Both channels (Telegram, Web) share 100% of the engine too.** Each channel builds the same `CheckInput` and calls the same `run_check()`. No analysis logic ever lives in a channel — the web layer only adds anonymous identity (a signed-cookie pseudonymous key instead of a Telegram ID) and the abuse controls Telegram provides for free (captcha, IP rate-limit, upload caps).

---

## 3. Pipeline stages (the contract every check follows)

`run_check(input: CheckInput) -> CheckResult` executes these stages in order. Each stage is pure-ish and unit-testable.

1. **intake** — normalize the Telegram update into a `CheckInput` (face, language, input_type, raw_text?, image_bytes?, caption?). Reject empty/unsupported early **without** an LLM call.
2. **ocr** — if image: strip EXIF/GPS, run OCR → `ocr_text` + `ocr_confidence`. If confidence < threshold → fail path "ask for pasted text" (no LLM call).
3. **rules** — run the face's rule pack over the **raw** text (`raw_text` or `ocr_text`) → `RuleHit[]` + `ExtractedSignals`. Authoritative facts.
4. **minimize** — produce `minimized_text` (PII values replaced by typed tokens, signal structure preserved).
5. **llm** — call the model with `minimized_text + rule_hits + signals + face + language + JSON schema` → `DraftOutput`.
6. **validate** — run the safety validator over `DraftOutput`. On fail: one retry with a stricter instruction; on second fail: `FALLBACK` (generic safe message, no analysis) and flag `safety_blocked`.
7. **format** — assemble the fixed output block in the target language.
8. **persist (no content)** — write a privacy-safe `check_event` + cost/latency; **delete the ephemeral workspace.**

Every stage records timing into the event. A failure at any stage returns a typed failure (see §6 `CheckStatus`) and still deletes content.

### 3.1 Language resolution (the analysis/reply language)

`CheckInput.language` is the language the rules, prompt, and reply use. Resolve it in this order:
1. **Content language wins.** Detect the dominant language/script of the analyzed text (`raw_text`/`ocr_text` + caption) using a lightweight detector (e.g. `langdetect` for RU vs UZ, plus a Cyrillic-vs-Latin character-ratio check to split `uz_cyrl` vs `uz_latn`). If confident, use it.
2. **Fallback** to the user's UI language chosen at consent.
3. On **code-switched** text (RU+UZ mixed — common here), pick the script/language of the majority of *words*, and instruct the prompt it may quote the other language verbatim. Add at least one code-switched fixture to the test set (§13 T7).

### 3.2 Caption & forwarded text

Merge an optional `caption` into the analyzed text (caption + body) before stages 3–5; it is ephemeral like all content. For forwarded messages, use the message text/caption only — **do not** attempt to resolve the forwarded sender's identity (no person lookup exists in this product).

---

## 4. Repository layout

```
avvalo/
├─ app/
│  ├─ main.py                 # entrypoint: start bot + scheduler
│  ├─ config.py               # pydantic Settings (env)
│  ├─ bot/
│  │  ├─ dispatcher.py        # aiogram setup, FSM storage
│  │  ├─ handlers.py          # /start, consent, input, feedback callbacks, /privacy, /delete_my_data
│  │  ├─ keyboards.py         # inline keyboards
│  │  ├─ texts.py             # ALL UI strings keyed by (key, language)
│  │  └─ states.py            # FSM states (ChoosingLang, AwaitingConsent, Ready, ...)
│  ├─ web/
│  │  ├─ app.py               # FastAPI app: GET / , POST /check , GET /privacy , GET /healthz
│  │  ├─ routes.py            # /check builds CheckInput → engine.run_check (SAME pipeline)
│  │  ├─ abuse.py             # Turnstile verify + IP/session rate-limit + upload-size cap
│  │  ├─ session.py           # signed-cookie anonymous pseudonymous key
│  │  ├─ templates/           # Jinja2: index.html, _result.html (HTMX partial), privacy.html
│  │  └─ static/              # minimal CSS + htmx.min.js
│  ├─ engine/
│  │  ├─ pipeline.py          # run_check() orchestration (§3)
│  │  ├─ types.py             # CheckInput, CheckResult, RuleHit, DraftOutput, ... (§6)
│  │  ├─ intake.py
│  │  ├─ faces.py             # Face config registry (§5)
│  │  ├─ ocr/{base.py,gcv.py,tesseract.py,local_stub.py}   # gcv=prod · tesseract=offline dev · local_stub=on-prem roadmap
│  │  ├─ minimize.py
│  │  ├─ rules/{engine.py,loader.py}
│  │  ├─ llm/{base.py,openai_compat.py,prompt.py}   # openai_compat = Qwen via neutral host (host-agnostic)
│  │  ├─ validate.py
│  │  └─ format.py
│  ├─ data/
│  │  ├─ db.py                # engine/session factory
│  │  ├─ models.py            # SQLAlchemy tables (§5 schema) — NO content columns
│  │  ├─ repo.py              # CRUD: consent, events, feedback, limits, deletion
│  │  └─ retention.py         # APScheduler TTL cleanup jobs
│  ├─ privacy/
│  │  ├─ user_key.py          # HMAC pseudonymous key
│  │  └─ consent.py           # consent versioning constant + helpers
│  └─ obs/
│     ├─ events.py            # log_event() — privacy-safe only
│     └─ cost.py              # token→cost accounting per provider
├─ rules/
│  ├─ family_shield/*.yaml    # 5 consumer families (§ rule format)
│  └─ seller_guard/*.yaml     # ~5 merchant families
├─ prompts/
│  ├─ system_safety.txt       # shared system prompt (output contract + prohibitions)
│  ├─ family_shield.txt       # consumer task template
│  └─ seller_guard.txt        # merchant task template
├─ tests/
│  ├─ fixtures/golden/*.json  # 5 FS + ≥3 SG golden examples
│  ├─ fixtures/adversarial/*.json
│  └─ test_*.py
├─ alembic/
├─ docker-compose.yml
├─ Dockerfile
├─ .env.example
├─ pyproject.toml
└─ README.md
```

---

## 5. Faces, config & database schema

### 5.1 Face registry (`engine/faces.py`)
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Face:
    id: str                  # "family_shield" | "seller_guard"
    rule_pack_dir: str       # "rules/family_shield"
    prompt_template: str     # "prompts/family_shield.txt"
    daily_limit: int         # FS=5, SG=20 (merchant checks more)

FACES = {
    "family_shield": Face("family_shield", "rules/family_shield", "prompts/family_shield.txt", 5),
    "seller_guard":  Face("seller_guard",  "rules/seller_guard",  "prompts/seller_guard.txt", 20),
}
```
Bot selection: simplest is **two bot tokens** (one per face) sharing one process and DB; `main.py` starts both dispatchers and tags each with its `Face`. (Alternative: one bot, a `/start` button to choose face — store the choice on the FSM. Two tokens is cleaner for the demo and lets you brand each.)

### 5.2 Database schema (PostgreSQL — **no content columns anywhere**)

```sql
-- consent: retain 12 months
consent(user_key TEXT, face TEXT, notice_version TEXT, language TEXT, ts TIMESTAMPTZ, PRIMARY KEY(user_key, face))

-- check_event: retain 90 days. NO submitted text, OCR text, output, URLs, names, usernames, file ids.
check_event(
  id UUID PK, user_key TEXT, face TEXT, ts TIMESTAMPTZ,
  input_type TEXT,            -- 'text' | 'image'
  language TEXT,              -- 'uz_latn' | 'uz_cyrl' | 'ru'
  rule_ids TEXT[],           -- IDs only, e.g. ['fs.urgency.deadline','fs.credential.otp']
  no_signal BOOLEAN,         -- true if "no warning signs" path fired
  status TEXT,               -- see CheckStatus
  error_class TEXT NULL,
  ocr_confidence REAL NULL,
  latency_ms INT, ocr_ms INT NULL, llm_ms INT NULL,
  input_tokens INT NULL, output_tokens INT NULL, cost_usd NUMERIC(10,6) NULL,
  safety_blocked BOOLEAN DEFAULT false
)

-- feedback: retain 90 days. categorical only.
feedback(check_id UUID PK, usefulness TEXT, next_action TEXT, ts TIMESTAMPTZ)  -- usefulness in {yes,partly,no}; next_action in {verify,delay_stop,continue,not_sure}

-- rate_limit: retain 48h
rate_limit(user_key TEXT, face TEXT, day DATE, count INT, PRIMARY KEY(user_key, face, day))

-- deletion_log: audit
deletion_log(user_key TEXT, requested_ts TIMESTAMPTZ, completed_ts TIMESTAMPTZ NULL)
```

`user_key = HMAC_SHA256(secret=APP_HMAC_SECRET, msg=str(telegram_user_id))[:32]` — never store the raw Telegram ID.

---

## 6. Core data types (`engine/types.py`)

Use pydantic models. These are the contracts; match field names exactly.

```python
from enum import Enum
from pydantic import BaseModel

class Language(str, Enum): uz_latn="uz_latn"; uz_cyrl="uz_cyrl"; ru="ru"
class InputType(str, Enum): text="text"; image="image"
class CheckStatus(str, Enum):
    ok="ok"; no_signal="no_signal"; empty_input="empty_input"
    low_ocr="low_ocr"; rate_limited="rate_limited"; timeout="timeout"
    llm_error="llm_error"; safety_fallback="safety_fallback"; unsupported_media="unsupported_media"

class CheckInput(BaseModel):
    face: str
    user_key: str
    language: Language
    input_type: InputType
    raw_text: str | None = None        # EPHEMERAL — never persisted
    image_bytes: bytes | None = None   # EPHEMERAL
    caption: str | None = None         # EPHEMERAL

class Signal(BaseModel):              # structured fact extracted locally, safe to send to LLM
    kind: str                         # 'link_lookalike','link_shortened','phone_new','card_personal','otp_request',...
    note: str | None = None           # short, generic, NO raw value

class RuleHit(BaseModel):
    rule_id: str                      # 'fs.credential.otp'
    family: str                       # 'credential_theft'
    message_key: str                  # key into a localized explanation
    severity: int = 1

class DraftOutput(BaseModel):         # what the LLM returns (JSON mode)
    red_flags: list[str]
    pattern: str | None
    verify: list[str]
    ask: list[str]

class CheckResult(BaseModel):
    status: CheckStatus
    text: str | None = None           # final formatted message (EPHEMERAL — returned, not stored)
    rule_ids: list[str] = []
    no_signal: bool = False
    safety_blocked: bool = False
    # metrics:
    language: Language
    input_type: InputType
    latency_ms: int = 0
    ocr_ms: int | None = None
    llm_ms: int | None = None
    ocr_confidence: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    error_class: str | None = None
```

---

## 7. OCR contract (`engine/ocr/`)

```python
# base.py
class OCRResult(BaseModel): text: str; confidence: float
class OCRProvider(Protocol):
    async def extract(self, image_bytes: bytes) -> OCRResult: ...
```
- `gcv.py` — Google Cloud Vision `DOCUMENT_TEXT_DETECTION`. Map page-level confidence to `confidence` (average word confidence is fine). **Strip EXIF/GPS before the call** (use Pillow: re-save without metadata). Verify SDK auth via service-account JSON in env. **Caution:** GCV detects Latin/Cyrillic at the *script* level so RU and UZ-Cyrl/UZ-Latn screenshots generally work, but Uzbek has no dedicated language model and no public benchmark — sanity-check OCR quality on real UZ screenshots during T8, and rely on the low-confidence "paste the text" fallback when it struggles.
- `tesseract.py` — **offline dev OCR** (`pytesseract` + Tesseract, CPU, with `rus` / `uzb` / `uzb_cyrl` language data). Selected by `OCR_PROVIDER=tesseract`. Lower quality than Cloud Vision — for key-free local dev only (§1.2), never the production default.
- `local_stub.py` — raises `NotImplementedError("on-prem OCR is post-grant roadmap")`. Exists so the swap is obvious.
- **Provider selection:** `OCR_PROVIDER` chooses the implementation (`gcv` default for prod, `tesseract` for offline dev). The pipeline only depends on the `OCRProvider` interface.
- Threshold: if `confidence < OCR_MIN_CONFIDENCE` (default 0.5) → pipeline returns `CheckStatus.low_ocr` (ask user to paste text). No LLM call.
- **The image is never sent to the LLM.** Only OCR text continues, and only after minimization.

---

## 8. LLM contract (`engine/llm/`)

```python
# base.py
class LLMResponse(BaseModel): draft: DraftOutput; input_tokens: int; output_tokens: int
class LLMProvider(Protocol):
    async def analyze(self, *, system: str, user: str, schema: dict, max_output_tokens: int) -> LLMResponse: ...
```
- `openai_compat.py` — call the host with the **OpenAI Chat Completions** API (`openai` SDK, `base_url=LLM_BASE_URL`, `api_key=LLM_API_KEY`, `model=LLM_MODEL`), **JSON mode** via `response_format={"type":"json_object"}`. Map the result into `DraftOutput`. `max_output_tokens` bounded (default 600). Temperature 0.2. One retry on transient error. This single adapter serves **Qwen, DeepSeek, or a self-hosted endpoint** — only env changes, no code. Pick a host with a **DPA + no-retention / no-training**; the request still sends only minimized text.
- `prompt.py` — `build_prompt(face, language, minimized_text, rule_hits, signals) -> (system, user)`:
  - **system** = contents of `prompts/system_safety.txt` (the shared output contract + prohibitions, see §9 list).
  - **user** = the face template (`prompts/{face}.txt`) filled with: target language, the minimized text, a bulleted list of rule hits rendered as their **neutral English `desc`** (the `loader` builds a `rule_id → desc` map from the YAML), the structured signals, and the instruction to return JSON matching the schema and to **write the final wording in the target language/script.** (The LLM translates/expresses the `desc`; it must not erase a hit or add one not supplied.)
- **Cost accounting** (`obs/cost.py`): `cost_usd = input_tokens/1e6 * IN_RATE + output_tokens/1e6 * OUT_RATE` using `LLM_IN_RATE_PER_M` / `LLM_OUT_RATE_PER_M`. Set the rates from the chosen host's Qwen pricing.

### Prompt hard constraints (must appear in `system_safety.txt`, all enforced again by the validator §9)
- Ground every red flag in the supplied text/signals; invent nothing.
- Output ONLY the JSON; ≤3 bullets per block; reply in the requested language/script.
- NEVER imply `safe`/`verified safe`/`scammer`/`fraudster`/`fraud confirmed`; no score/verdict.
- NEVER claim to have checked an identity, bank, phone, URL reputation, database, or website.
- NEVER repeat a full card/OTP/password/passport/secret.
- NEVER tell the user to open the link, scan the QR, call the number in the message, or reply to "test" the sender.
- NEVER invent facts, policies, contact details, prices, or legal conclusions.
- (Seller Guard) NEVER state that money arrived/was received based on a screenshot.

### 8.1 Model selection — current default + eval gate

**Research snapshot, 2026-07-01:** use **OpenRouter first** for hosted-model validation, with Zero Data Retention enforced. The current best default to evaluate is `qwen/qwen3-235b-a22b-2507`: OpenRouter lists it as a multilingual Qwen3 235B A22B Instruct model, non-thinking mode, OpenAI-compatible, with `response_format` / structured-output support, and current list pricing around `$0.09/M` input and `$0.10/M` output tokens. At Avvalo's prompt shape (~1k input tokens, bounded ≤600 output tokens), this is far below the `$0.03/check` hard ceiling.

Recommended alpha env:

```env
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=qwen/qwen3-235b-a22b-2507
LLM_IN_RATE_PER_M=0.09
LLM_OUT_RATE_PER_M=0.10
```

Fallbacks to evaluate:

| Candidate | Why try it | Use if |
|---|---|---|
| `qwen/qwen3-235b-a22b-2507` via OpenRouter ZDR | Best current balance: open-weight Qwen, strong multilingual odds, cheap, JSON/structured-output support | It passes Uzbek/Russian quality, JSON, latency, and safety evals |
| `qwen/qwen3-32b` via OpenRouter ZDR | Smaller/faster Qwen fallback, also cheap | 235B latency or availability is poor |
| `google/gemini-2.5-flash-lite` via paid/ZDR route | Cheap non-Qwen comparator | Qwen Uzbek quality fails or JSON reliability is poor |
| Local `qwen2.5:7b-instruct` via Ollama | Zero API cost and best privacy for dev plumbing | Local smoke tests only; Uzbek quality is not enough to decide production |

Do **not** choose the cheapest model blindly. Direct DeepSeek pricing is competitive, but its public privacy posture is a poor fit for Avvalo's trust story; avoid direct DeepSeek for production unless a separate no-training/no-retention contract exists. The long-term roadmap remains self-hosted Qwen in-region behind the same OpenAI-compatible adapter.

Before locking any model, run `tools/eval_models.py` (self-contained; see its header). It calls every configured provider — Gemini, DeepSeek, Qwen, and any local OpenAI-compatible endpoint — with the real prompts over the 8 golden fixtures, and scores a mechanical rubric (valid JSON, correct script, no verdict words, no leaked contacts, structure, length). It cannot score whether the *advice is good* — read `eval_out/<provider>/` by eye for that, especially the Uzbek outputs. Pick the cheapest provider that passes the rubric **and** reads as natural, grounded Uzbek. The chosen provider is just one `LLMProvider` adapter (§8); the rest of the engine does not change. See [V1_BUILD_SCOPE.md](V1_BUILD_SCOPE.md) §4 (item 5) for why Uzbek quality — not price — is the deciding factor.

---

## 9. Safety validator (`engine/validate.py`) — safety-critical, specify exactly

`validate(draft: DraftOutput, signals: list[Signal], rule_hits: list[RuleHit], language: Language) -> ValidationResult`

Run these **deterministic** checks over the concatenated draft strings:

1. **Verdict words** — reject if any banned token appears (maintain a per-language banned list: e.g. RU «безопасно/мошенник/афёрист», UZ-Latn «xavfsiz/firibgar», UZ-Cyrl «хавфсиз/фирибгар», EN safe/scammer/fraud). Use word-boundary, case-insensitive matching.
2. **Hallucinated / leaked contacts** — extract every phone number, URL/domain, email, and card-like digit run from the draft via regex. Because **all** such identifiers are minimized to tokens *before* the LLM ever sees the text (§10), a correct output contains **none** of them. Therefore the rule is simple and strong: **reject if the draft contains any raw phone, URL/domain, email, or card-like number at all.** This catches both leaked input values and fabricated "official" contacts in one check — the model has no legitimate reason to emit a raw identifier. (Allow generic references like "the bank's official app" — those have no digits/domains.)
3. **Unsafe instruction** — reject if the draft tells the user to open/click/follow the link, scan the QR, call/write the number from the message, or "reply to check." (Keyword patterns per language.)
4. **Secret leakage** — reject if the draft contains a full PAN (13–19 digit run), an OTP-looking 4–8 digit code labeled as code, or "password/parol/пароль" followed by a value.
5. **Structure** — reject if `verify` or `ask` is empty. `red_flags` may be empty **only** on the no-signal path (below); otherwise reject if empty. A block exceeding 3 bullets is **truncated** (not rejected) for length.

**Determining `no_signal`:** set `no_signal = (len(rule_hits) == 0 and len(draft.red_flags) == 0)`. On this path `format.py` prepends the mandatory *"No clear warning signs were found in the content provided. This does not prove that the situation is safe."* lead (localized) and still renders `verify`/`ask`. The prompt MUST tell the LLM that an empty `red_flags` list is correct when nothing concrete is found — it must never invent a flag to fill the block.

**Fail-action:** on any reject → **one** retry of the LLM call appending the failed-check reason to the system prompt. If the retry also fails validation → return `CheckStatus.safety_fallback` with a generic safe message (localized): *"We couldn't produce a safe explanation for this one. Do not share codes or pay before independently verifying through an official app/number you find yourself."* Set `safety_blocked=true`. **A repeated person-level accusation or secret leak in production = pause the bot** (alert the operator).

`format.py` then appends the mandatory **limitation line** per language (the "Avvalo analyzed the situation, not the person; did not certify safety" line from the golden examples) and the leading **"No clear warning signs…"** sentence when `no_signal` is true.

---

## 10. Minimization (`engine/minimize.py`)

`minimize(raw_text: str, signals: list[Signal]) -> str`

- Replace, in the text sent to the LLM: phone numbers → `[PHONE]`, card/account numbers → `[CARD]`, emails → `[EMAIL]`, @usernames / t.me links → `[HANDLE]`, full personal names (best-effort) → `[NAME]`, street addresses → `[ADDRESS]`, OTP/codes → `[CODE]`.
- **URLs:** replace the raw URL with a token that carries the *signal*, derived by the rule engine, e.g. `[LINK: lookalike-domain]` or `[LINK: shortened]` or `[LINK]` if no signal. Do **not** pass the raw domain.
- Keep everything else verbatim (the scam's wording is the analysis material).
- The **rule engine (run before minimize) is what classifies** links/phones/cards into signals; minimize just substitutes. This keeps the LLM able to explain a flag without seeing the raw identifier.
- Unit-test: given a message with a phone + lookalike URL + card, the output contains `[PHONE]`, `[LINK: lookalike-domain]`, `[CARD]` and none of the raw values.

---

## 11. Rule engine & rule format

### Rule file (`rules/<face>/<family>.yaml`)
```yaml
family: credential_theft           # maps to a RuleHit.family
rules:
  - id: fs.credential.otp
    message_key: otp_request
    desc: "Message asks for an SMS/OTP code; legitimate staff never ask for it."  # neutral English meaning passed to the LLM
    severity: 2
    match:                          # ANY group matching => hit; keywords are per-language
      uz_latn: ["sms kod", "6 xonali kod", "kodni yuboring"]
      uz_cyrl: ["смс код", "кодни юборинг"]
      ru: ["код из смс", "пришлите код", "одноразовый код"]
    emits_signal: otp_request       # optional: adds a Signal
  - id: fs.urgency.deadline
    message_key: urgency_deadline
    match:
      uz_latn: ["10 daqiqada", "hozir", "faqat bugun"]
      uz_cyrl: ["10 дақиқада", "ҳозир", "фақат бугун"]
      ru: ["в течение часа", "сейчас же", "только сегодня"]
```
- `engine.py`: `run_rules(text, face) -> (hits: list[RuleHit], signals: list[Signal])`. Lowercase + normalize the text per language; match keyword/regex groups; dedupe by `rule_id`. Also run **structural extractors** (regex for URLs/phones/cards) that classify into `Signal`s (lookalike = brand-name-substring heuristic or known-brand list; shortened = known shortener domains; card-personal = transfer-to-card phrasing nearby).
- `loader.py`: load all YAML in the face's `rule_pack_dir` at startup; validate schema; expose by face. **A YAML file uses a top-level `families:` list** (each entry has `family:` + `rules:`); the loader flattens all families across all files in the directory. (The shipped packs `rules/family_shield/families.yaml` and `rules/seller_guard/families.yaml` use this shape.) Each rule carries `id`, `desc` (neutral English meaning → the prompt), `message_key`, `severity`, optional `emits_signal`, and a `match` block with `uz_latn`/`uz_cyrl`/`ru` keyword lists.
- **Authoritative:** a rule hit is a fact. The LLM may explain/dedupe but may not erase or invent one (enforced by passing hits as grounded input and by the validator not removing them).

### Required rule families
- **Family Shield (5):** `credential_theft`, `urgency_secrecy`, `authority_impersonation`, `upfront_payment`, `verification_avoidance` (+ `implausible_promise`, `suspicious_link_qr` from the guide's 7 — include all 7 if cheap). Source: [FAMILY_SHIELD_VALIDATION.md](FAMILY_SHIELD_VALIDATION.md) §8.
- **Seller Guard (~5):** `receipt_inconsistency` (amount/date/bank fields don't line up), `amount_mismatch` (order total ≠ claimed paid), `edited_screenshot_hint` (textual signs only — font/spacing claims; do NOT do image forensics in v1), `fake_courier_refund` (chat patterns), `verify_in_bank_app` (always-emit reminder family).

---

## 12. Privacy, retention & deletion (`data/retention.py`, `privacy/`)

- **Ephemeral workspace:** download image to a temp file in a dedicated dir; OCR; then **delete immediately** in a `finally` block. Never write `raw_text`, `ocr_text`, `minimized_text`, or `draft` to disk/DB/logs.
- **Logging discipline:** the logger MUST refuse content. Provide `log_event(name, **fields)` in `obs/events.py` that only accepts the allowed fields (language, input_type, face, rule_ids, latency, tokens, cost, error_class, status) and raises if given anything named like content. Allowed event names: `consent_shown, consent_accepted, check_started, check_completed, check_failed, usefulness_answered, decision_answered, share_tapped, deletion_requested, deletion_completed`.
- **TTL jobs (APScheduler daily):** delete `check_event`/`feedback` > 90d, `consent` > 365d, `rate_limit` > 48h, `deletion_log` per policy. Content has no DB row, so nothing to TTL there.
- **`/delete_my_data`:** delete all rows for `user_key` across consent/events/feedback/limits within the request; write `deletion_log`; confirm to user. (Spec allows up to 7 days; do it immediately here.)
- **`/privacy`:** print the localized privacy notice (what's processed, 1-hour content deletion, model boundary, no certification, how to delete).
- **Consent gate:** no content is processed until `consent` row exists for `(user_key, face)` at the current `NOTICE_VERSION`. Bump `NOTICE_VERSION` → re-consent.

---

## 13. Build sequence (numbered tasks with acceptance criteria)

Build in this order. Each task is independently testable.

**T1 — Skeleton & config.** Repo layout (§4), `pyproject.toml`, `config.py` (env via pydantic-settings), `.env.example`, Alembic init, and `docker-compose.yml` with services **`db`** (Postgres 16), **`app`** (bot + FastAPI web in one image), and an optional GPU **`ollama`** behind a `local-llm` profile (§1.2):
```yaml
services:
  db:
    image: postgres:16
    environment: { POSTGRES_DB: avvalo, POSTGRES_USER: avvalo, POSTGRES_PASSWORD: ${POSTGRES_PASSWORD} }
    volumes: ["pg:/var/lib/postgresql/data"]
  ollama:                                  # optional local LLM:  docker compose --profile local-llm up
    image: ollama/ollama:latest
    profiles: ["local-llm"]
    ports: ["11434:11434"]
    volumes: ["ollama_models:/root/.ollama"]
    gpus: all                              # uses the registered nvidia runtime
    restart: unless-stopped
  app:                                     # Telegram bot + FastAPI web (same process)
    build: .
    environment:
      DATABASE_URL: postgresql+asyncpg://avvalo:${POSTGRES_PASSWORD}@db:5432/avvalo
      LLM_BASE_URL: ${LLM_BASE_URL:-http://ollama:11434/v1}   # defaults to local; override to the hosted Qwen
      LLM_API_KEY: ${LLM_API_KEY:-ignored}
      LLM_MODEL: ${LLM_MODEL:-qwen2.5:7b-instruct}
    depends_on: [db]
    ports: ["8080:8080"]                   # web app
volumes: { pg: {}, ollama_models: {} }
```
*Accept:* `docker compose up` starts `db` + `app` (app boots and connects to the DB); `docker compose --profile local-llm up` additionally starts Ollama and the app reaches it at `http://ollama:11434/v1`; `ruff` clean.

**T2 — DB models & repo.** Implement §5.2 schema in `models.py`, Alembic migration, `repo.py` CRUD, `user_key.py` HMAC.
*Accept:* migration applies; unit test creates consent + event rows; **no content column exists** (assert by inspecting the schema in a test).

**T3 — Bot shell & consent flow.** aiogram dispatcher, FSM states, `/start` → language pick → privacy notice → consent → "Ready"; `/privacy`, `/delete_my_data`; `texts.py` strings in all 3 languages.
*Accept:* a manual run lets a user consent and reach the input prompt; consent row written with version+timestamp+language; `/delete_my_data` removes it.

**T4 — Engine types & pipeline skeleton.** `types.py` (§6), `pipeline.run_check` wired with stub stages returning canned data; `faces.py`.
*Accept:* `run_check` on a text input returns a `CheckResult` through all stages; ephemeral fields never touch DB (test asserts event row has no text).

**T5 — Rule engine + Family Shield rules.** `rules/engine.py`, `loader.py`, the FS YAML families (§11), structural signal extractors, `minimize.py` (§10).
*Accept:* unit tests: each FS golden input fires the expected `rule_ids`; minimization tokenizes PII and preserves link signal; the 5 golden raw inputs each yield ≥1 rule hit.

**T6 — LLM integration.** `llm/base.py`, `gemini.py` (JSON mode), `prompt.py`, `prompts/*.txt`, `obs/cost.py`.
*Accept:* given minimized text + rule hits for golden example 1, the model returns a `DraftOutput`; cost is computed and recorded; output is in the requested language/script.

**T7 — Safety validator + format.** `validate.py` (all §9 checks), `format.py` (assemble block + limitation line + no-signal lead).
*Accept:* validator rejects crafted bad drafts (verdict word; fabricated phone; "open the link"); on double-fail returns `safety_fallback`; the 5 FS golden outputs pass validation and match the golden structure/facts (wording may differ, facts/actions/safety must not).

**T8 — OCR.** `ocr/base.py` interface + `OCR_PROVIDER` selection; `ocr/gcv.py` (prod) and `ocr/tesseract.py` (offline dev); EXIF strip; low-confidence path; `local_stub.py` placeholder.
*Accept:* with `OCR_PROVIDER=gcv`, an image of golden example 3 (UZ-Cyrl) OCRs to usable text → full pipeline produces a valid output; with `OCR_PROVIDER=tesseract` the same image runs **offline** (lower quality acceptable); a blurry image returns `low_ocr` with no LLM call; EXIF is stripped (test on a GPS-tagged image).

**T9 — Limits, feedback, share, events.** Daily limit per face; post-check feedback buttons → `feedback` rows; share button (link only); wire all privacy-safe events.
*Accept:* 6th FS check same day is refused with a reset message; feedback recorded categorically; events emitted for the full happy path; logger rejects a content field (test).

**T10 — Seller Guard face.** SG rule pack (§11), `prompts/seller_guard.txt`, SG entry copy, and shared engine wiring.
*Accept:* ≥3 SG golden examples (author them in `tests/fixtures/golden`) pass end-to-end; SG output **never** says money arrived; same engine path used (assert pipeline code is unchanged).

**T11 — Retention jobs & metrics export.** APScheduler TTL jobs; a protected `metrics` query/CLI that returns event counts, activation, completion, cost, no-signal fire-rate.
*Accept:* TTL job deletes an artificially-aged row; metrics command prints the privacy-safe aggregate the pitch needs.

**T12 — Hardening & demo polish.** Timeouts (p90 budget §14), one retry on LLM/transient, graceful failure messages, README with run + demo script.
*Accept:* the §15 demo script runs clean end-to-end in both faces, all 3 languages, text + image.

**T13 — Web client (bot + web).** A FastAPI app in the same process, sharing the engine and DB. `GET /` renders a page with a language selector, a face toggle (Family Shield default), a consent gate, a text box, and an image upload. `POST /check` builds a `CheckInput` and calls **the same `run_check()`** — no analysis logic in the web layer — and returns the result as an HTMX partial. `GET /privacy`. Image upload is gated by **Cloudflare Turnstile**; all checks are **IP/session rate-limited** (reuse the `rate_limit` table with a web `user_key` = HMAC of a signed session cookie). Reuse `bot/texts.py` for the three languages. Web is **anonymous** — no accounts, no history. *(Can be built any time after T10; it adds zero engine logic.)*
*Accept:* a web check returns the **same structured output as the bot** for the same input (assert both paths call `run_check`); image upload fails without a valid Turnstile token; the per-day limit refuses extra checks; **no submitted content is persisted** (same guarantee as the bot — verified by test); the consent notice is shown before the first check; all three languages render.

---

## 14. Cost & performance budget (enforce in code)

- Model = Flash-tier; `max_output_tokens` ≤ 600; temperature 0.2; **one** retry max.
- Bounded prompt: send only minimized text + rule hits + signals (not the raw image, not history).
- **Targets:** blended ≤ $0.015/check, hard ceiling ≤ $0.03; single check ≤ $0.05 after one retry.
- **Latency:** p90 ≤ 30s text, ≤ 45s image. Wrap OCR and LLM calls in `asyncio.wait_for`; on timeout → `CheckStatus.timeout`, offer one retry, give no safety conclusion.
- Record `input_tokens, output_tokens, cost_usd, latency_ms, ocr_ms, llm_ms` on every event. A daily metrics line shows blended cost; alert if it drifts above ceiling.
- **Do not** reduce cost by removing rules, minimization, or the validator.

---

## 15. Definition of done + IT Park demo script

**Done when** all §13 acceptance criteria pass and:
- both faces run on the identical pipeline (only rule pack + template differ);
- **both channels (Telegram bot + web app) call the same `run_check()` and return matching output;**
- 5 FS + ≥3 SG golden examples pass; safety test set fully blocked;
- no submitted content in any DB/log/backup (verified by test + manual log inspection) — on bot **and** web;
- web image upload is captcha-gated and all web checks are rate-limited;
- p90 latency and ≤$0.03 cost hold on a 50-check sample;
- `/privacy` + `/delete_my_data` work; metrics export returns the pitch numbers.

**Demo script (rehearse this for the grant panel):**
1. *Family Shield:* forward the fake-bank-support message (UZ-Latn) → instant 🚩/✅/❓ in Uzbek. Show it never says "scammer."
2. Send a screenshot of the seller-prepayment scam (UZ-Cyrl image) → OCR → same structured read in Cyrillic.
3. *Seller Guard:* forward a payment-screenshot order → merchant checklist; point out it says **"verify in your bank app,"** never "money received."
4. *Web app:* open the URL, run the same Family Shield check anonymously → identical output; show the Turnstile-gated image upload. (One engine, two channels.)
5. Show `/privacy` + `/delete_my_data`, then the **metrics export** (checks, languages, cost/check).
6. Close on the platform story: one engine, two faces, two channels — roadmap = on-prem OCR + self-hosted model + payment-provider API + more faces.

---

## 16. Explicit non-goals for the implementer (do not build)

Graph/entity/person lookup · "reported N×" · accusation storage · subscriptions/payments/team accounts · payment-provider integration · mobile / browser-extension clients (the **web app IS in scope** — T13) · web accounts/login (web is anonymous in v1) · image forensics / reverse-image search · URL fetching / malware scanning / external reputation calls · any persistence of submitted content · a full admin UI. If a task seems to require one of these, stop and flag it — it's out of scope by design ([PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) §14, [V1_BUILD_SCOPE.md](V1_BUILD_SCOPE.md) §2).

---

*Build order, contracts, and acceptance criteria above are the spec. When external APIs (Gemini, Cloud Vision, aiogram) differ from what's described, follow the current official docs for the call details but keep the interfaces in §6–§9 unchanged.*
