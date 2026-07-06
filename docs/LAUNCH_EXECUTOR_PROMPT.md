# Avvalo — Launch-Phase Executor Prompt (R1–R4 + R6)

> Copy everything below the line into the session that will build the launch features, or just tell it:
> *"Read docs/LAUNCH_EXECUTOR_PROMPT.md and execute it, starting at R1."*
> It assumes repository access. Architecture decisions here were made 2026-07-06 against the real code; where this doc and [ROADMAP.md](ROADMAP.md) disagree on mechanics, this doc wins (it corrects stale facts); where they disagree on *scope or safety*, ROADMAP and [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) win.

---

You are the implementing engineer for **Avvalo** (see `CLAUDE.md` for the system map). v1 is **deployed to production** (bot @Avvalo_official_bot + web); there are zero real users yet. You are building the **launch feature set**: the viral loop, the findability surface, the consented story corpus, the trend export, and one engine upgrade (URL reputation). Everything reuses the existing engine; nothing forks it.

## Read first, in order
1. `docs/ROADMAP.md` — the task list this prompt executes (R1–R4; R6 is added here).
2. `docs/PRODUCT_GUIDE.md` — safety rules; they override everything.
3. `docs/ML_RESEARCH.md` §3–§4, §7 — why R3 and R6 are shaped the way they are.
4. Skim `docs/PRODUCT_VISION.md` §4 and `docs/PRODUCT_HORIZONS.md` §7 for the why.

## Non-negotiables (unchanged from the build era, one new exception)
- **Never persist or log submitted content** — with exactly **one sanctioned exception**: R3 stores the **minimized** story text after explicit user consent. Nothing else. If you are about to store any other user-supplied string, stop.
- **No verdicts, no risk scores, no "checked a database" claims** — except R6's blocklist line, which is allowed *because* it is a sourced statement of fact about a URL (an artifact, not a person), phrased as "appears in a public phishing blocklist", never "this is a scam".
- **Pipeline order stays:** rules on raw local text → signals → minimize → LLM → validate. R6 inserts a *local* lookup between rules and minimize; it sends nothing anywhere.
- Every user-facing string in **all three languages** (`uz_latn`, `uz_cyrl`, `ru`).
- Every tunable via `Settings` (`app/config.py`) + `.env.example`. Providers injectable for tests.
- **Do not touch** `prompts/*` safety wording or weaken rule packs; extend only.
- Do-not-build list unchanged: person lookup, open forum, payments, mobile app, new faces, deepfake/image-forensics claims.

## Branch & deploy discipline (critical)
**Pushing `main` deploys to production.** Work on branch `launch-features`, one task per commit (or PR per task). Do **not** merge to `main` until the founder has recorded Phase A verification in `docs/ops/SMOKE_2026-07.md`. At session start: if that file is missing, create it from ROADMAP Phase A (A1–A8) as an unchecked checklist, mark which items only the founder can run (Telegram flows, prod DB, prod logs), then proceed with R1 on the branch — building doesn't need the smoke to pass; deploying does.

## Corrections to stale roadmap facts (verified 2026-07-06)
- `rules/family/families.yaml` has **7** families, not 11: `credential_theft`, `urgency_secrecy`, `authority_impersonation`, `upfront_payment`, `verification_avoidance`, `implausible_promise`, `suspicious_link_qr`. Derive R2 slugs from the YAML at startup — never hardcode a slug list.
- The metrics CLI **exists at `app/tools/metrics.py`** (module `app.tools.metrics`) — R4 **extends** it; do not create a second CLI under `tools/`. *(Corrected 2026-07-06: an earlier version of this line claimed it didn't exist.)*
- `app/bot/keyboards.py` already has a placeholder share button (`DEFAULT_SHARE_URL = "https://t.me/share/url?text=Avvalo"`, used in `post_check_keyboard`). R1 replaces it, not adds alongside it.
- `CheckResult.check_id` is already populated by the pipeline after event recording, and `check_event.rule_ids` is already persisted — R1 rides on these.
- Config already has `notice_version = "2026-06-24-v1"` and `operator_alert_chat_id` (unused so far — R3 uses it).

---

## R1 — "Forward this warning" share button (~0.5 day)

**Goal:** one tap turns a scared user into a distributor, with a share text that is content-free **by construction**.

**Architecture (decided):**
- New renderer `share_summary(rule_ids, language, face) -> str` in `app/engine/format.py`. Built **only** from deterministic material: localized scam-family display names (new 3-language mapping keyed by family, derived from the rule packs' family ids — add to `app/bot/texts.py` or a shared texts module) + a fixed CTA line with the bot deep link (`https://t.me/Avvalo_official_bot`). **Never** LLM prose, never user text — that is what makes "no user content" provable rather than filtered. Cap at top 3 families by max severity. No rule hits → generic localized text ("I checked a suspicious message with Avvalo — check yours").
- Keyboard: in `post_check_keyboard`, replace the static URL button with callback button `share:<check_id>` (only when a `check_id` exists; fall back to the plain bot-link share URL otherwise).
- Handler (`app/bot/handlers.py`): on `share:` callback → load the event via a new `repo.get_check_event(session, check_id)` → rebuild `share_summary` from its persisted `rule_ids`/`language`/`face` (nothing stored, nothing new persisted) → log `log_event("share_clicked", face=…, language=…)` → answer the callback and send one message containing the summary plus an inline URL button `https://t.me/share/url?url=<bot-link>&text=<urlencoded summary>`. Two taps total; no inline-mode/BotFather config needed.

**Acceptance:** unit test over every golden fixture in `tests/fixtures/golden/*.json` asserts the share text contains no fixture input text, no digits longer than 4, no `@`/`+998`/URL other than the bot link; works in all three languages; `share_clicked` emitted (assert via log capture); callback flow tested with a fake bot; unknown/expired `check_id` answers gracefully.

## R2 — Scam library: public education pages (~1–2 days code + drafts)

**Goal:** the only UZ-language scam content hub; every page funnels into the checker. Zero engine code touched.

**Architecture (decided):**
- Content: `content/scams/<lang>/<slug>.md`, slug = family id from `rules/family/families.yaml` (7 today, auto-derived). Front matter: `title`, `description`, `published: false`. Sections: how it works · red flags · what to do · "check yours now" CTA (web form + bot link).
- New `app/web/content.py`: front-matter parse + markdown render (add the `markdown` package as a dependency — sanctioned) with mtime-based cache so editing needs no redeploy.
- Routes in `app/web/routes.py`: `GET /scams` (localized index), `GET /scams/{slug}` (uses the web app's existing language mechanism; `hreflang` alternates; missing translation falls back to an available language with a small notice), `GET /sitemap.xml` (published pages only). Pages get long `Cache-Control`. `published: false` pages 404 outside debug — that flag is the founder's review gate 👤.
- Templates: `scam_index.html`, `scam_page.html` per the existing Jinja2 style.
- Drafts: write RU + UZ-Latin drafts for all 7 slugs, grounded in each family's `desc` + keywords and `docs/ADJACENT_PRODUCT_IDEAS.md` patterns. Neutral tone, no verdict words, situations-not-persons. Leave all `published: false`; the founder reviews and flips 👤. UZ-Cyrillic when translated later.

**Acceptance:** route tests for every slug × available language; fallback path tested; sitemap lists only published; content-presence test (each family slug has ru + uz_latn drafts); no imports from `app/engine` added to web content code.

## R3 — Opt-in story capture (~2–3 days) ⚠️ the one persistence exception

**Goal:** consented, minimized, founder-reviewed stories — channel fuel now, the ML corpus later ([ML_RESEARCH.md](ML_RESEARCH.md) §7: similarity search ships at ~100 approved stories; that future feature needs only `minimized_text`/`language`/`face`/`status`, so no extra columns now).

**Architecture (decided):**
- Bot-only in this pass (the trigger — positive feedback — exists only in the bot). Trigger: after `feedback:usefulness:yes|partly` → invite with "Share what happened (anonymous)" / "No thanks" buttons → aiogram FSM state captures the next text message (length cap `STORY_MAX_CHARS`, default 2000; one story per `check_id`; small daily cap per user — all in `Settings`).
- Flow: story text → `run_rules(text, face)` for signals → `minimize(text, signals)` → show the user the **minimized** version → explicit "Publish anonymously" consent tap → store → forward the minimized text to `operator_alert_chat_id` (skip with a warning log if unset) → thank the user. Cancel available at every step; raw text lives only in the FSM state and is dropped on every exit path.
- `repo.store_story(...)` **re-runs minimize internally on whatever it receives** — the repo layer never trusts the caller. Stores minimized text only.
- Schema: `story_submission(id UUID pk, user_key, face, language, minimized_text, status: submitted|approved|rejected|published, created_ts, reviewed_ts)` + Alembic migration.
- `tests/test_schema_privacy.py`: update **deliberately** to allowlist exactly `story_submission.minimized_text`, with a comment marking it a reviewed decision; assert everything else stays content-free.
- Privacy notice: add the story-capture paragraph in all three languages, **bump `notice_version`** (e.g. `2026-07-XX-v2`) — verify the consent gate then forces re-consent for existing users.
- `/delete_my_data` also deletes the user's `story_submission` rows; retention job purges `rejected` stories after `STORY_REJECTED_RETENTION_DAYS` (default 30).
- Founder review CLI: `tools/stories.py list|approve|reject` (async session, argparse; `published` reserved for later). No admin UI.
- ⚖️ Leave a visible TODO for the lawyer checkpoint (PRODUCT_VISION §9.3) — do not treat it as done.

**Acceptance:** unit test proving raw (un-minimized) text can never reach the DB even if the handler passes it raw; consent-flow test (no store without the explicit tap); deletion test; retention test; operator forward mock-tested; re-consent-after-bump test; CLI smoke test.

## R4 — Scam Pulse + feedback-as-labels (~1 day)

**Goal:** turn already-collected metadata into a monthly authority artifact and a free model-quality signal ([ML_RESEARCH.md](ML_RESEARCH.md) §8 row 1 — "build now, zero new collection").

**Architecture (decided):**
- Create `tools/metrics.py` with two subcommands, both **read-only**:
  - `pulse --month YYYY-MM`: aggregates `check_event` — rule-family (map rule id → family via the loaded rule packs) × language × face counts, month-over-month deltas, no-signal rate, totals → `out/pulse_YYYY-MM.md` (`out/` gitignored). Founder pastes into the channel 👤.
  - `labels [--since YYYY-MM-DD]`: joins `feedback` × `check_event` on `check_id` — per-rule-id usefulness rates and `next_action` distribution vs the overall baseline; flags rules whose useful-rate sits well below baseline (candidates for rewording/expansion). This is the weak-label loop from ML_RESEARCH §7.
- Output contains **counts only** — no `user_key`, no ids; asserted in tests.

**Acceptance:** seeded in-memory-DB tests with exact expected counts for both subcommands; an output-privacy test greps the rendered markdown for key patterns (uuids, user_key values); runs against prod DB via the normal env config.

## R6 — URL reputation stage (~2 days; new task, from [ML_RESEARCH.md](ML_RESEARCH.md) §4)

**Goal:** the cheapest real detection lift — "this link appears in a public phishing blocklist (source, listed since …)" as a grounded fact.

**Architecture (decided):**
- **Local feeds only. No per-check external API call, ever** — sending a user's URL to Google/PhishTank would leak submitted content, so the Safe Browsing *Lookup* API is rejected on privacy grounds (the hash-prefix Update API is deferred as complexity not worth it for v1; note this in the module docstring).
- Sources: URLhaus dump + OpenPhish feed (both free; URLs via env settings) + **our own UZ list** `rules/shared/uz_phishing_domains.yaml` (founder-curated, git-versioned, human-readable — this becomes the unique data asset).
- Storage: new table `url_blocklist(domain_hash sha256-hex, source, first_seen, last_seen)` — store **hashes of normalized domains/URLs from the public feeds**, not raw strings, so the schema-privacy test stays honest and lookups (exact-match) lose nothing. Alembic migration; PK (domain_hash, source).
- Refresh: an APScheduler job next to the retention job — download feeds every `URL_FEEDS_REFRESH_HOURS` (default 12), normalize (lowercase, strip scheme/`www.`, punycode-decode), upsert hashes. Whole stage behind `URL_REPUTATION_ENABLED` (default `false` — founder flips it in prod after verifying feed downloads work from the VM).
- Pipeline placement (`app/engine/pipeline.py::_run_stages`): after `run_rules`, before `minimize`/LLM. Take URLs/domains from the link signals the extractors already emit from raw text, normalize + hash, batch-lookup locally. On hit, append a synthetic `RuleHit` (`shared.link.blocklisted`, severity 3, desc carrying source + first-seen) — it then flows through the existing prompt-grounding, validator, formatting, and `rule_ids` logging (so Pulse picks it up) with **zero new output pathways**. The validator already strips raw links from output, so the user sees the fact of listing, never the URL echoed back.
- Provider behind a small interface with a fake for tests, like OCR.

**Acceptance:** hit and no-hit golden tests with a fake blocklist store; normalization tests (scheme/www/punycode/case); refresh-job unit test with a fake HTTP layer; disabled-flag test (stage is a no-op); schema-privacy test still passes; output line exists in all three languages and never contains the raw URL.

---

## How to work
- One task at a time, in order **R1 → R2 → R3 → R4 → R6**. R6 is independent — pull it earlier if you're blocked waiting on founder review of R2/R3 material. R5 (STT eval) is **not** in this prompt: it needs founder-recorded voice samples; you may draft the 10 scam-scenario scripts for it as a parting artifact if time remains.
- A task is done when its acceptance criteria demonstrably pass: `pytest -q` and `ruff check .` green, new tests included, `.env.example` updated, ROADMAP checkbox ticked. *(ROADMAP's "11 slugs" was already corrected to 7 on 2026-07-06.)*
- After each task, report: what you built, which criteria pass and how verified, decisions made, anything flagged.
- Founder-only steps are marked 👤 — prepare materials, never fake them (no auto-publishing content, no fabricated review).
- Ask before adding any dependency beyond `markdown`, or any architectural pattern not named here.

Begin by confirming you've read ROADMAP.md and PRODUCT_GUIDE.md, restate R1 in your own words, then start.

---

*Mirrors ROADMAP.md R1–R4 and ML_RESEARCH.md §3–§4/§7–§8 as of 2026-07-06; update this prompt if those change.*
