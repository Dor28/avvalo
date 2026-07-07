# Avvalo — Roadmap: Launch Phase (post-deployment)

> **Status:** Executable roadmap for the next work sessions (human or agent) · 2026-07-04
> **Context:** v1 is **built and deployed to production with live API tokens** (bot [@Avvalo_official_bot](https://t.me/Avvalo_official_bot); web stack per [DEPLOYMENT.md](DEPLOYMENT.md)). Zero real users so far. Strategy is locked: [PRODUCT_VISION.md](PRODUCT_VISION.md) §4 is the plan of record; [PRODUCT_HORIZONS.md](PRODUCT_HORIZONS.md) §7 is the ranked build order; this doc turns both into numbered, verifiable tasks.
> **Authority chain:** safety rules in [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) override everything · [V1_TECHNICAL_PLAN.md](V1_TECHNICAL_PLAN.md) remains the engineering contract for the existing surface · this roadmap governs *what to do next*.

---

## 0. For the next session/agent — read this first

Read, in order: this doc → [PRODUCT_VISION.md](PRODUCT_VISION.md) → [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) (safety rules) → skim [V1_CURRENT_PM_REVIEW.md](V1_CURRENT_PM_REVIEW.md). The build-era constraints in [archive/EXECUTOR_PROMPT.md](archive/EXECUTOR_PROMPT.md) still apply (that prompt is archived — it drove the completed T1–T13 build; this roadmap replaces it as the active handoff); the critical ones, restated:

1. **Never persist submitted content** — with exactly **one new sanctioned exception**: task R3's opt-in story capture stores the **minimized** text only, after explicit user consent, pending founder review. Nothing else changes. If you are about to store any other user-supplied string, stop.
2. **Safety output contract:** no verdicts ("safe"/"scammer"/"fraud confirmed"), no risk scores, no claims of checking external databases, no raw contacts/PII in output.
3. **Pipeline order stays:** rules on raw local text → signals → minimize → LLM. One engine, all channels; no analysis logic in a client.
4. **Do not touch** the safety prompts or weaken rule packs without flagging; extend, don't rewrite.
5. **Do not build** anything on the do-not list ([PRODUCT_HORIZONS.md](PRODUCT_HORIZONS.md) §7): person lookup, open forum, payments, mobile app, new faces.
6. Work **one task at a time**, in order; each task ends with its acceptance criteria demonstrably passing (tests where code, artifacts where content).

**Founder-only tasks are marked 👤** — an agent prepares materials for them but must not fake them (no invented interviews, no auto-posting to the channel).

---

## Phase A — Verify the live deployment (do first, ~half a day)

Deployment happened; verification hasn't. Nothing in Phase B starts until every box below is checked against **production**.

- [ ] **A1. Health:** `curl https://<domain>/healthz` returns ok; bot answers `/start` in Telegram.
- [ ] **A2. Full bot flow, three languages:** for `uz_latn`, `uz_cyrl`, `ru` — /start → consent → text check → result → feedback buttons work. Use the golden-example inputs from [FAMILY_VALIDATION.md](FAMILY_VALIDATION.md) §7.
- [ ] **A3. Image path live:** one real screenshot per script through the bot; OCR confidence logged; low-quality image returns the `low_ocr` path, not a crash.
- [ ] **A4. Live LLM quality:** run `python tools/eval_models.py` against the production model config; **manually read the Uzbek outputs** (natural? grounded? correct script? no verdict words?). If Uzbek is broken, flag and stop — model choice reopens.
- [ ] **A5. Web channel:** if `WEB_ENABLED=true` — anonymous text check on `/` and `/merchants`; consent enforced before processing; Turnstile fires on image upload; over-limit path returns the friendly message.
- [ ] **A6. Privacy audit on prod:** inspect DB (`consent`, `check_event`, `feedback`, `rate_limit`, `deletion_log`) — zero submitted content anywhere; `docker logs` contain no user text/PII; `/delete_my_data` works end-to-end.
- [ ] **A7. Ops flags:** `WEB_COOKIE_SECURE=true`, secrets not in repo, retention job scheduled (check APScheduler log line), DB backups actually running (restore-test one), cost-per-check logging populated and ≤ $0.03, p90 latency ≤ 30s text / 45s image.
- [ ] **A8. Set `OPERATOR_ALERT_CHAT_ID`** to the founder's chat (it's wired in config but unused — R3 will use it).

Deliverable: a short `docs/ops/SMOKE_2026-07.md` (or session report) recording pass/fail per item with evidence.

---

## Phase B — Launch features (build in this order)

### R1. "Forward this warning" share button — ~0.5 day
**Status:** [x] Code complete on branch `launch-features` (2026-07-06); do not merge to `main` until Phase A smoke evidence is recorded.

On every successful check result, add an inline button that shares a **sanitized summary** (pattern name + top red flags + "check yours: t.me/Avvalo_official_bot") via Telegram's share/switch-inline mechanism. Note: a placeholder already exists (`DEFAULT_SHARE_URL` in `app/bot/keyboards.py`, used by `post_check_keyboard`) — **replace it**, don't add a second button.
**Files:** `app/bot/keyboards.py`, `app/bot/handlers.py`, `app/engine/format.py` (a `share_summary()` renderer), `app/bot/texts.py` (3 language forms).
**Acceptance:** shared text contains no user content and no PII (unit test over golden fixtures); deep link opens the bot; works in all three languages; share taps counted as a privacy-safe event (`share_clicked`) in `check_event`-style logging (no content).

### R2. Scam library — public education pages — ~1–2 days code + content
**Status:** [x] Code complete on branch `launch-features` (2026-07-07); markdown drafts are intentionally `published: false` until founder review.

Server-rendered pages on the web app: `GET /scams` (index) and `GET /scams/<slug>` — one page per **family rule family** (7 slugs — derive from `rules/family/families.yaml` at startup, never hardcode the list), each: how the scam works · red flags · what to do · "check yours now" CTA (web form + bot link). Content lives as markdown files under `content/scams/<lang>/<slug>.md` so editing needs no redeploy.
**Languages:** RU + UZ-Latin first; UZ-Cyrillic when content is translated. Agents draft content from the rule families + [archive/ADJACENT_PRODUCT_IDEAS.md](archive/ADJACENT_PRODUCT_IDEAS.md) patterns; **founder reviews every page before publish** 👤.
**Files:** `app/web/routes.py`, new template `scam_page.html`, `content/scams/…`, sitemap route for SEO.
**Acceptance:** all slugs render in available languages with correct hreflang; missing translation falls back gracefully; pages are static-cacheable; zero engine code touched; route tests added.

### R3. Opt-in story capture — ~2–3 days ⚠️ the one consented persistence exception
**Status:** [x] Code complete on branch `launch-features` (2026-07-07); requires founder/operator review flow and lawyer checkpoint before public alpha.

After positive feedback (`usefulness` = yes/partly), offer: *"Share what happened — anonymously — to warn others?"* Flow: user writes story → **pipe through the existing minimizer** (`app/engine/minimize.py`) → show the user the minimized version → explicit "publish anonymously" consent tap → store → forward to `OPERATOR_ALERT_CHAT_ID` for review.
**Schema:** new table `story_submission(id UUID, user_key, face, language, minimized_text, status: submitted|approved|rejected|published, created_ts, reviewed_ts)` + Alembic migration.
**Guardrails (all mandatory):**
- Only the **minimized** text is ever stored — enforce in repo layer (store function runs minimize itself; never trusts the caller).
- `tests/test_schema_privacy.py` currently asserts **no** table holds content — update it **deliberately** to allowlist exactly `story_submission.minimized_text` and assert everything else stays content-free. This test is the guardrail; treat the edit as a reviewed decision, not a fix.
- Privacy notice gains a story-capture paragraph → **bump `NOTICE_VERSION`** (forces re-consent) → texts updated in all three languages.
- `/delete_my_data` deletes the user's stories too; retention rule added (e.g., rejected stories purged in 30 days).
- ⚖️ Flag for the lawyer checkpoint before public alpha ([PRODUCT_VISION.md](PRODUCT_VISION.md) §9.3).
- TODO (lawyer): confirm the R3 privacy-notice wording, retention terms, and operator/founder review process before public alpha.
**Acceptance:** unit tests prove raw text can never reach the DB; consent flow test; deletion test; operator forward mocked-tested; founder can approve/reject via a simple CLI (`tools/stories.py list|approve|reject`) — no admin UI in this pass.

### R4. Scam Pulse — aggregate trend export — ~1 day
Extend `app/tools/metrics.py` (CLI) with `pulse --month YYYY-MM`: aggregates `check_event.rule_ids` frequency by rule family × language × face, month-over-month deltas, no-signal rate, total checks — rendered to a markdown one-pager (`out/pulse_YYYY-MM.md`). Also export the **rule-hit × feedback correlation** (which rule families users mark useful / act on) — the free active-learning signal for tuning rules ([ML_RESEARCH.md](ML_RESEARCH.md) §7).
**Acceptance:** runs read-only against prod DB; output contains counts only (zero user identifiers — assert in test); founder can paste the output into a channel post 👤.

### R5. Uzbek STT evaluation — gate for voice checks — ~1 day
Mirror `tools/eval_models.py`: `tools/eval_stt.py` testing 2–3 STT providers (e.g., Whisper-family API + one alternative) on ~10 UZ-Latin-speech / UZ-RU code-switched / RU voice samples (founder records them 👤 — 30–60s each, scam-scenario scripts provided by agent).
**Acceptance:** a decision memo `docs/ops/STT_EVAL.md` with WER-style notes and a go/no-go. **Only a "go" unlocks building voice intake** (spec in [PRODUCT_HORIZONS.md](PRODUCT_HORIZONS.md) §3.1) — do not implement voice checks in the same session as the eval.

### R6. URL reputation stage — ~2–3 days (from [ML_RESEARCH.md](ML_RESEARCH.md) §4)
A lookup stage after signal extraction: check extracted URLs against **Google Safe Browsing** (use the hash-prefix Update API so raw URLs never leave the server), cached **URLhaus** and **OpenPhish** feeds (TTL-refreshed), and a new `uz_phishing_domain` table (domains only — privacy-safe) seeded from checks users later confirm as scams.
A hit becomes a rule-grade authoritative signal → output line: *"this link appears in a phishing blacklist [source]"* (factual, sourced — allowed by the safety contract; a *miss* must never be reported as "link is clean").
**Files:** new `app/engine/reputation.py` stage wired into the pipeline after signal extraction; config keys for the GSB key + feed URLs + cache TTLs.
**Acceptance:** mocked-feed tests for hit/miss/feed-down paths; feed outage degrades gracefully (no crash, no "clean" claim, no latency blowup — budget ≤ +2 s); no full URL sent to any third party; the blacklist line renders in all three languages.
*Scope note:* this deliberately supersedes the v1 build's exclusion of "external reputation calls" ([V1_TECHNICAL_PLAN.md](V1_TECHNICAL_PLAN.md) §16) — that list governed the grant build, not this phase. Do not stop-and-flag on that ground.

---

## Phase C — Launch ops (parallel with Phase B; mostly 👤 with agent support)

| # | Task | Owner | Agent support |
|---|---|---|---|
| C1 | Create the public Telegram channel; enable comments | 👤 | Agent drafts channel description + pinned post (3 language forms) |
| C2 | First 10 channel posts ("scam of the week" + education) | 👤 posts | Agent drafts from rule families + scam library content; founder edits voice |
| C3 | Alpha recruitment (60–100 users per [FAMILY_VALIDATION.md](FAMILY_VALIDATION.md) §2, with the cohort fixes from [V1_CURRENT_PM_REVIEW.md](V1_CURRENT_PM_REVIEW.md) P1.1) | 👤 | Agent drafts invite message, onboarding guide, and the delayed-outcome follow-up question |
| C4 | Merchant interviews — 5/week toward 20, named price, dated pilot ask (script: [V1_CURRENT_PM_REVIEW.md](V1_CURRENT_PM_REVIEW.md) §6) | 👤 | Agent drafts outreach DM, a one-page Avvalo Merchants pitch (UZ/RU), and an interview-notes template |
| C5 | IT Park application | 👤 submits | Agent drafts the application narrative: engine + two faces + two channels + scam library + Pulse + privacy posture ("verify situations, not persons") |
| C6 | Lawyer checkpoint: privacy notice, story capture (R3), operator entity | 👤 | Agent prepares the question list from [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) §12 |

---

## Phase D — Evidence gates (decide, don't drift)

Set calendar dates for these when Phase B lands; each gate has a pre-committed consequence:

1. **Alpha gate** (21 measured days; [FAMILY_VALIDATION.md](FAMILY_VALIDATION.md) §11 + PM-review metric additions): repeat-use and usefulness pass → invest in Learn/Share growth; fail → stop consumer polish, all-in on merchants or rethink.
2. **Merchant gate:** ≥3 independent merchants accept a named price with a dated paid pilot → **only then** build billing (Payme/Click) and promote Avvalo Merchants to the lead product. Fewer → Merchants stays a demo face.
3. **Horizons pull-forward:** any [PRODUCT_HORIZONS.md](PRODUCT_HORIZONS.md) idea may start only if its §6 criteria all hold — engine reuse · nameable payer · situations-not-persons · founder capacity.
4. **Content cadence check (honesty gate):** after 4 weeks — if fewer than ~2 posts/week actually shipped, consciously drop the Learn/Share layer rather than half-run it ([PRODUCT_VISION.md](PRODUCT_VISION.md) §8.2).
5. **Corpus milestones → ML unlocks** ([ML_RESEARCH.md](ML_RESEARCH.md)): ≥ **100** founder-reviewed R3 stories → build the **pattern-similarity evidence** feature (HORIZONS §3.4; retrieval, no training) · ≥ **300–500** → SetFit first-pass classifier on an Uzbek encoder (HORIZONS §5.2). Both match *patterns, never people*; neither may ship a verdict.

---

## Definition of done for this roadmap

Phase A all green · R1–R4 + R6 live in production (R5 memo written) · channel exists with ≥8 posts · alpha recruiting started · ≥10 merchant interviews logged · IT Park application submitted. At that point, write the next roadmap **from evidence** — usage data, interview notes, and gate outcomes — not from strategy discussion. The failure mode to avoid is documented in [PRODUCT_VISION.md](PRODUCT_VISION.md) §8: more documents than users.
