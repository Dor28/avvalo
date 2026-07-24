# Avvalo — Current Roadmap

> **Status:** Active order of work
> **Last updated:** 2026-07-25
> **Product authority:** [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md)

## Why this order

The engine is built and deployed. The safety chassis — deterministic validator, PII minimization,
pseudonymous keys, retention, no-verdict rule — is the hard, unglamorous half, and it is done.

Two things are not built, and neither is code:

1. **Local knowledge.** The shipped baseline is 13 rules and 10 knowledge cards describing
   *universal* scam patterns — OTP requests, urgency, prepayment. Nothing in them is specifically
   Uzbek. Until real circulating Uzbek scam material is encoded, a user gets an answer a
   general-purpose assistant could also produce, and Avvalo has no reason to exist.
2. **Users.** Nothing downstream can be decided without them. The Verify gates require 60 activated
   users and 150 real checks; distribution is currently at zero.

So the order below puts the founder-only work first and treats code as the *support* for it, not
the other way round. Phase 1 is deliberately small: it closes real correctness gaps and makes the
detection assets editable as data, so Phase 2 does not require an engineer.

Everything about the Verify gate stays as it was — the discipline there is right. What changed is
what comes *before* it.

## 0. Rules for every work session

1. Read [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) first.
2. Work on one phase and one acceptance boundary at a time.
3. Never persist or log submitted content — decoded QR payloads and extracted URLs are submitted
   content.
4. Never output a verdict or score.
5. Never claim an official source was checked without a typed Avvalo Verify result. Link and QR
   wording is shape-based only ("this address imitates…", "shortened links hide…"); the sole
   sourced URL fact remains `shared.link.blocklisted`.
6. Do not create an implementation task for a feature that has not passed its product gate.
7. `main` deploys to production; merge only with explicit founder authorization and passing
   automated checks.

## Phase 1 — Make the checker's assets editable and its link analysis correct (code)

### 1.1 QR decoding at intake — **done**

- [x] Local in-process QR decoding beside OCR in the content stage, via `zxing-cpp`. No system
      packages, no network, no external service.
- [x] Decoded payload treated exactly like submitted text; EMVCo-style payment payloads raise a
      typed `Signal`, never a parsed merchant claim.
- [x] Unreadable and multi-QR images degrade honestly.
- [x] Golden fixtures for payment-page URL, shortened URL, lookalike domain, non-URL text, and an
      unreadable code.
- [x] Decoded payloads are ephemeral: minimized before the LLM, never persisted, logged, or fetched.

### 1.2 One URL analyzer — **done**

- [x] A single normalizer ([app/engine/url.py](../app/engine/url.py)) shared by rule matching,
      `minimize()`, and reputation lookup. The three stages previously disagreed: a punycode or
      Cyrillic imitation was a lookalike to one and invisible to another.
- [x] Coverage: punycode and mixed-script lookalikes, IP-literal hosts, `userinfo@` tricks,
      public suffixes used as interior labels (`click.uz.evil.example`), shorteners, `hxxp`
      defanging.
- [x] The no-fetch invariant is tested: no code path performs a network request to a submitted
      destination.
- [x] A regression guard fails the build if a submitted-content stage grows its own host pattern
      again.

### 1.3 The official-domain catalog — **the highest-value asset in this document**

Ships as data at [rules/shared/official_domains.yaml](../rules/shared/official_domains.yaml),
loaded by the analyzer with an in-code floor so detection can never fall to zero.

- [x] Mechanism built and tested; the 14 organizations already in the codebase were migrated into
      it unchanged.
- [ ] **Founder:** extend to the ~20 most impersonated organizations in Uzbekistan. Each entry
      needs every real domain the organization uses, confirmed from the organization's own
      published materials. A missing real domain produces false "lookalike" labels.

This one file does three jobs: it is lookalike detection today, it is the seed for Avvalo Verify
§4.1 (official identity match) later, and it is a large part of the Phase 3 validation packet.
Build it once, early. It requires no code change and no deploy of new logic.

### 1.4 Truthful copy

- [ ] Align `image_hint` texts with what the checker actually does now.
- [ ] Review link/QR knowledge cards in both reply languages (`uz_latn`, `ru`).

### Deferred out of Phase 1

**URL reputation enablement.** `rules/shared/uz_phishing_domains.yaml` currently contains zero
domains, so the store has nothing to match and enabling it would change no answer. It stays behind
`URL_REPUTATION_ENABLED=false` until there is a maintained feed worth consulting. Reconsider after
Phase 2 produces real scam material — the domains found there are the natural first entries.

**Phase 1 exit:** suite + ruff green; deployed; founder verifies a real QR photo and a lookalike
URL end-to-end in the production bot; the catalog covers the top ~20 organizations.

## Phase 2 — Real Uzbek scam material (founder, no code)

This is the moat. Nothing here needs an engineer.

- [ ] Collect **30–40 scam messages actually circulating in Uzbekistan** — from personal networks,
      Telegram channels, and public warnings. Never from user submissions: those are ephemeral by
      design and must stay that way.
- [ ] Encode each one as rules and knowledge cards through `/admin/rules` and `/admin/cards`
      (needs `ADMIN_ACCESS_KEY` configured in production — do this first). Both editors have a
      dry-run against the real matcher, so a preview cannot drift from production.
- [ ] Add the hardest cases to `tests/fixtures/golden/checks.json` so detection quality cannot
      silently regress.
- [ ] Write the first three to five educational cases in both reply languages, drawn from the same
      material.

Cases are manually authored education. They are not Avvalo Verify evidence, a public allegation
database, public submissions, comments, ratings, or automatic derivatives of user checks.

**Phase 2 exit:** the rule pack covers materially more than the universal patterns it ships with,
and the founder can name the local scam types Avvalo explains better than a general assistant.

## Phase 3 — Distribution and the answer format (founder, no code)

Runs alongside Phase 2 and gates everything after it.

- [ ] **30 real users.** Seed the bot where the scams actually circulate.
- [ ] **Sit with five of them while they read a real answer.** Did they read to the end? What did
      they do next? Was anything confusing? The answer contract has never been tested against a
      person under time pressure on a phone; if it needs to change, better to learn it now than
      after Verify is built on top of it.
- [ ] **Measure return rate within 14 days.** At this scale it is the only number that means
      anything — it says whether the habit is forming. Coverage and completion rates are vanity
      until then.

**Phase 3 exit:** a written founder judgment on whether people come back, and any answer-format
changes that came out of watching them read.

## Phase 4 — Official registry verification (Avvalo Verify)

Unchanged in substance. Starts after Phase 3. No feature code before a recorded `go`.

### 4a. Manual validation packet ([VERIFY_VALIDATION.md](VERIFY_VALIDATION.md))

- [ ] 30 representative scenarios: 10 per family — official identity match; official domain and
      QR-destination catalog match; regulated organization and license routing. Draw them from the
      Phase 2 material; do not invent scenarios that no one has actually encountered.
- [ ] Founder-reviewed source inventory (registries, regulator lists, official domain catalogs).
- [ ] Deterministic evidence wording in both reply languages.
- [ ] Advice-only and evidence-backed answer pair for every scenario; paired user sessions with
      categorical results.
- [ ] Explicit `go`, `revise once`, or `stop` decision, recorded in writing.

Gate for `go`: at least 40% decision-relevant evidence coverage, at least 70% preference for the
evidence-backed answer, and zero invented, overstated, unsourced, or person-level facts.

> **Expect an uneven result.** The curated official-contact catalog is likely to clear the bar;
> live register integrations may not, on permissions and access rather than on engineering. If the
> packet says "the catalog works, the registers do not", that is a real answer — ship the catalog
> half rather than reaching for a fourth family to rescue the average.

### 4b. Strict MVP (only after a recorded `go`)

One executor-ready task under `docs/tasks/`. It defines typed evidence (stable ID, source,
retrieved-at, limitations), approved sources, refresh and failure behavior, privacy boundaries,
wording in both reply languages, adversarial tests, migrations if required, and rollout flags.
It must not include general web browsing or another product feature.

### 4c. Measured alpha

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

The roadmap is complete when Phase 1 is live and verified in production, the catalog covers the
top organizations, real Uzbek scam material is encoded and covered by goldens, the first cases are
published, 30 users have been observed and a return rate recorded, the Phase 4a packet has a
recorded decision, and — on `go` — the strict MVP is live and audited and the measured alpha
reaches its sample with a written decision from the agreed metrics.
