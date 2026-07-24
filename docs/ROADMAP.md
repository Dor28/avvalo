# Avvalo — Current Roadmap

> **Status:** Active order of work
> **Last updated:** 2026-07-24
> **Product authority:** [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md)

This roadmap contains one product path only. Order of work, decided by the founder on 2026-07-24:
first make every intake the checker already advertises genuinely work — links and QR codes
analyzed by **shape**, with no official-source claims — then validate and build official-registry
verification (Avvalo Verify). This pulls the *deterministic* half of PRODUCT_GUIDE §4.2 (local QR
decoding, URL normalization, local reputation lookup) forward into the explainer; the
*source-backed* half (official catalog comparison, registry facts) stays behind the
[VERIFY_VALIDATION.md](VERIFY_VALIDATION.md) gate.

## 0. Rules for every work session

1. Read [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) first.
2. Work on one phase and one acceptance boundary at a time.
3. Never persist or log submitted content — decoded QR payloads and extracted URLs are submitted
   content.
4. Never output a verdict or score.
5. Never claim an official source was checked without a typed Avvalo Verify result. Phase 1 wording
   is shape-based only ("this address imitates…", "shortened links hide…"); the sole sourced URL
   fact remains `shared.link.blocklisted`.
6. Do not create an implementation task for a feature that has not passed its product gate.
7. `main` deploys to production; merge only with explicit founder authorization and passing
   automated checks.

## Phase 1 — Working explainer for links and QR codes (code, now)

Goal: a user sends a raw link, a screenshot containing a link, or a photo of a QR code, and gets
the same grounded explanation the text path gives — the destination analyzed by shape only, never
opened, rendered, or fetched.

### 1.1 QR decoding at intake

- [x] Decode QR payloads locally, in-process, from submitted images — beside OCR in the content
      stage of `app/engine/pipeline.py`. Candidate library: `zxing-cpp` (pip wheels for
      linux/windows, offline, Apache-2.0). No system packages, no network, no external service.
- [x] Decoded payload is treated exactly like submitted text: URL payloads flow through the URL
      rules; non-URL payloads flow through the normal text path; EMVCo-style payment payloads
      raise a typed `Signal`, never a parsed merchant claim.
- [x] Unreadable or multi-QR images degrade honestly (reuse low-confidence messaging; any new
      `CheckStatus` is added to the allow-set in `app/data/repo.py`).
- [x] Golden fixtures: QR PNGs covering a payment-page URL, a shortened URL, a lookalike domain,
      non-URL text, and an unreadable code — wired into the e2e goldens
      (`tests/fixtures/golden/checks.json`).
- [x] Privacy: decoded payloads are ephemeral like `raw_text` — minimized before the LLM, never
      persisted, never logged, never fetched.

### 1.2 One URL analyzer

- [ ] A single normalizer shared by rule matching (`app/engine/rules/engine.py`), `minimize()`,
      and reputation lookup. Today `app/engine/url_reputation/normalize.py` is stronger than the
      main classifier — unify on the strong one instead of maintaining two.
- [ ] Coverage: punycode and mixed-script lookalikes, IP-literal hosts, `userinfo@` tricks,
      deceptive multi-label subdomains (`bank.uz.evil.com`), shorteners, `hxxp` defanging.
- [ ] The no-fetch invariant stays tested: no code path performs a network request to a submitted
      destination.

### 1.3 URL reputation, operator-reviewed

- [ ] Dry-run the existing local hash-based store (`app/engine/url_reputation/`) against recent
      rule-hit patterns, then decide prod enablement. Feed updates remain operator-approved.
- [ ] Wording stays within `app/engine/validate.py` allowances; no new claim forms.

### 1.4 Truthful copy and explanation quality

- [ ] Bot and web copy already promise QR support — this phase makes the promise true; align
      `image_hint` texts with actual behavior.
- [ ] Knowledge cards for link/QR situations reviewed in both reply languages (`uz_latn`, `ru`).

**Phase 1 exit:** full suite + ruff green; new goldens pass; deployed; founder verifies a real QR
photo and a lookalike URL end-to-end in the production bot.

## Parallel founder track — Cases and distribution (no code)

- [ ] Founder configures `ADMIN_ACCESS_KEY` in production.
- [ ] Founder writes, reviews, and publishes the first three to five cases in both reply languages.
- [ ] Seed the bot where the scams circulate; watch `share_tapped` / `share_clicked` and return
      usage. Phase 3's alpha needs 60 activated users — this pipeline fills slowly, start now.

Cases are manually authored education. They are not Avvalo Verify evidence, a public allegation
database, public submissions, comments, ratings, or automatic derivatives of user checks.

## Phase 2 — Official registry verification (Avvalo Verify)

Starts after Phase 1 ships. No feature code before a recorded `go`.

### 2a. Manual validation packet ([VERIFY_VALIDATION.md](VERIFY_VALIDATION.md))

- [ ] 30 representative scenarios: 10 per family — official identity match; official domain and
      QR-destination catalog match; regulated organization and license routing.
- [ ] Founder-reviewed source inventory (registries, regulator lists, official domain catalogs).
- [ ] Deterministic evidence wording in both reply languages.
- [ ] Advice-only and evidence-backed answer pair for every scenario; paired user sessions with
      categorical results.
- [ ] Explicit `go`, `revise once`, or `stop` decision, recorded in writing.

Gate for `go`: at least 40% decision-relevant evidence coverage, at least 70% preference for the
evidence-backed answer, and zero invented, overstated, unsourced, or person-level facts.

### 2b. Strict MVP (only after a recorded `go`)

One executor-ready task under `docs/tasks/`. It defines typed evidence (stable ID, source,
retrieved-at, limitations), approved sources, refresh and failure behavior, privacy boundaries,
wording in both reply languages, adversarial tests, migrations if required, and rollout flags.
It must not include general web browsing or another product feature.

### 2c. Measured alpha

- [ ] 60 activated users; 150 completed real checks; 30 users with a full 14-day return window.
- [ ] At least 30 consented or supervised fact-quality audits.
- [ ] Metrics calculated exactly as defined in `VERIFY_VALIDATION.md`.
- [ ] Founder records `continue`, `revise once`, or `stop`.

The alpha passes only with at least 35% evidence coverage, at least 98% audited fact precision,
zero critical false facts, at least 70% evidence usefulness, at least 25% decision impact, complete
source/time attribution, and zero privacy incidents.

## Not on the roadmap

- Avvalo Merchants;
- user-generated stories, comments, ratings, accusation feeds, or aggregate trend feeds;
- voice, group monitoring, family accounts, or new product faces;
- pattern similarity, classifiers, or training on submissions;
- autonomous browsing, reverse-image search, or authenticity verdicts;
- fetching, rendering, or executing any submitted URL or QR destination;
- bank, telco, marketplace, payment, escrow, or white-label integrations;
- billing or a final revenue model.

These items require a new founder decision backed by evidence. They must not be pulled into a task
because they appear in git history or a superseded document.

## Definition of roadmap complete

The roadmap is complete when Phase 1 is live and verified in production, the first cases are
published, the Phase 2a packet has a recorded decision, and — on `go` — the strict MVP is live and
audited and the measured alpha reaches its sample with a written decision from the agreed metrics.
