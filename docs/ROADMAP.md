# Avvalo — Current Roadmap

> **Status:** Active order of work
> **Last updated:** 2026-09-01
> **Product authority:** [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md)

## 0. How this roadmap works

This document answers one question: **what is built next, and how do we know it is done.**

It deliberately does not answer *when*. There are no dates, no estimates, and no capacity
arithmetic anywhere in it. One person builds one thing at a time; a number attached to that
is a guess that hardens into a broken promise and then quietly starts driving decisions it
was never accurate enough to drive. What replaces it is sequence: each phase states what it
unlocks, and nothing moves until the phase before it has cleared its exit criteria. §5
records the tests used to order the work when a choice is genuinely open.

Two facts set the order:

1. **The scanner engine is already written.** [app/engine/url.py](../app/engine/url.py)
   produces six deterministic shape labels with no model call, and
   [app/engine/qr/](../app/engine/qr/) decodes QR codes locally. Today both run only as
   invisible stages before an LLM call. Exposing them is the smallest change in this
   document and by far the most visible.
2. **The Mini App is a hard dependency for camera capture, and nothing else.** Photo-based
   QR and link analysis already work through the existing bot and web. So Phase 1 ships real
   product before any new shell exists.

### Rules for every work session

1. Read [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) first.
2. Work one phase and one acceptance boundary at a time.
3. Never persist or log submitted content — decoded QR payloads, extracted URLs, and
   resolved redirect destinations are submitted content.
4. Never output a verdict or a score. Decisiveness goes into the recommended action.
5. Redirect resolution stays inside the boundaries in PRODUCT_GUIDE §8.1. It must not widen
   into fetching page content.
6. Do not create an implementation task for anything in §8 or §9.
7. `main` deploys to production; merge only with explicit founder authorization and passing
   automated checks.

## 1. Phase 1 — The scanner answer

Ships through the **existing** bot and web. No Mini App required. This is the first time a
user sees an answer that costs nothing and returns instantly.

| # | Task |
|---|---|
| 1 | Short scanner answer path: a submitted link resolves through the existing analyzer and returns the three-state answer (PRODUCT_GUIDE §5.2) without a model call and without consuming `DAILY_CHECK_LIMIT` |
| 2 | Surface the official-domain catalog comparison in that answer — the classification already runs, it just never reaches the user |
| 3 | Payment-QR handling: recognise the EMVCo-shaped payload already detected as a `payment_qr` signal and return what to check before paying, never a parsed merchant claim |
| 4 | Redirect resolution for shorteners, exactly to the boundaries in PRODUCT_GUIDE §8.1 |
| 5 | "Need a full analysis?" — one action from the short answer into the existing chat check |

**Wording is the real work in tasks 1–3.** Six labels × two languages × three states, each
phrased as a shape observation plus a safe action, none of them a verdict. Draft in
`uz_latn` and `ru`, and have the Uzbek reviewed by a native speaker before release.

**Unlocks:** an answer with no marginal cost, which is the only kind that can be used
casually and repeatedly. Everything downstream — the Mini App shell, the funnel metric, the
family-group entry — assumes this exists.

**Exit:** a real lookalike URL, a real shortened URL, and a photographed payment QR each
return the short answer end to end in production; suite and `ruff check .` green; no new
code path fetches a submitted destination outside §8.1.

## 2. Phase 2 — The application

| # | Task |
|---|---|
| 6 | Telegram Mini App shell: three tabs (Scanner · Check · Knowledge), shared session, one engine behind all entries |
| 7 | QR capture through Telegram's built-in scanner |
| 8 | Onboarding in both languages: first screen, consent, language choice |
| 9 | Return and funnel metrics — scanner-to-check conversion, repeat visits within 14 days |

**Confirm before starting task 7:** the exact Mini App scanner API and its minimum Bot API
version, against current Telegram documentation. The plan assumes Telegram exposes its
scanner to Mini Apps and that we never write our own camera. If that assumption is wrong,
the shape of the task changes materially and it should be re-planned rather than forced.

**Task 9 is not optional instrumentation.** It is the only thing in this roadmap that
produces the evidence an investor actually reads, and the only thing that can tell this
document it has the order wrong. A feature list is not traction.

**Unlocks:** camera capture at the moment of payment — the situation the product is for —
and the first real measurement of whether the answer is worth returning to.

**Exit:** the three tabs work on a real phone in both languages; a check started in the
Scanner can be continued in the Check tab; return rate is being recorded.

## 3. Phase 3 — Reach

| # | Task |
|---|---|
| 10 | **Cyrillic-Uzbek output.** Detection and matching already handle it; only the reply is Latin-only. This opens the product to the group most exposed to fraud |
| 11 | First-run examples: three real cases in one tap, for the user who arrives with nothing suspicious in hand |
| 12 | Wave notification: opt-in storage, a throttled sender, an opt-out command, and a founder compose surface |
| 13 | Forwardable one-screen reminder ("five things a bank never asks") |

**Task 10 is the highest-value item in this phase** and the only one that adds no capability
at all. It converts "deliberately broad audience" from a statement into a fact.

**Task 12 is larger than it looks.** There is no broadcast infrastructure in the codebase
today — no opt-in column, no sender, no rate limiting against Telegram's delivery limits.
Build it small: a boolean per `user_key` (no content), a throttled loop, and an explicit
opt-out. Two to three sends a month, founder-authored, never automatically generated from
user checks.

**Unlocks:** the audience the product claims to serve. Until task 10 ships, reach work in
Phase 4 multiplies a product that half the intended users cannot comfortably read.

**Exit:** an older Cyrillic-reading user can complete a check start to finish; one wave
notification has been sent and opted out of successfully.

## 4. Phase 4 — Distribution

Both items multiply what already exists, so neither is worth building before answer quality
is confirmed by the Phase 2 metrics.

| # | Task |
|---|---|
| 14 | Family-group behaviour: the bot answers **only** on a direct mention or a forwarded message. It never reads a group passively — that would be chat surveillance and is incompatible with PRODUCT_GUIDE §8 |
| 15 | Inline mode: check a link inside an ongoing conversation without leaving it |

**Unlocks:** the product reaching people who would never install it themselves — one family
member adds it, and the people most likely to be targeted are covered without ever choosing
to be.

**Exit:** the bot has been added to a real family group and answered correctly without
responding to unrelated traffic.

## 5. What decides what comes next

With no estimates to weigh against each other, ordering rests on three tests, applied in
this order:

1. **Does it need something that does not exist yet?** Camera capture needs the Mini App
   shell; the wave notification needs opt-in storage before it needs a sender; every funnel
   number needs a scanner answer to funnel from. A task whose dependency is unbuilt is not
   ready, whatever its value.
2. **Does it improve the answer, or only its reach?** Answer quality compounds; reach
   multiplies whatever quality already exists. That is the whole reason Phase 4 is last —
   distributing a thin answer more widely is not progress, it is exposure.
3. **Would the content track (§6) make it redundant?** Several tempting features are
   requests for better detection assets wearing an engineering costume. If a rule, a card,
   or a catalog entry would solve it, it is content work and belongs in §6.

The one input that can legitimately reorder this document is evidence from real use, which
is what task 9 exists to produce. Until then the order above is an argument, not a
measurement, and should be treated as revisable rather than settled.

## 6. Content track — runs in parallel, founder only, no engineer

This is the moat, and no phase above compensates for its absence. It is gated on nothing:
none of it waits for a phase, and all of it can start before Phase 1 does. The shipped
baseline is 13 rules, 10 knowledge cards, 14 catalog organizations, and 13 golden cases —
all universal patterns, nothing specific to Uzbekistan.

- [ ] **Extend the official-domain catalog** at
      [rules/shared/official_domains.yaml](../rules/shared/official_domains.yaml) from 14 to
      the ~20 most impersonated organizations. Every real domain an organization uses,
      confirmed from its own published materials — a missing real domain produces false
      "lookalike" labels. Data only: no code change, no deploy of new logic.
- [ ] **Collect 30–40 scam messages actually circulating in Uzbekistan** and encode them as
      rules and cards through `/admin/rules` and `/admin/cards` (set `ADMIN_ACCESS_KEY` in
      production first). Both editors dry-run against the real matcher. Never source this
      from user submissions — those are ephemeral by design.
- [ ] **Write the "it already happened" knowledge**: money transferred, code received,
      account stolen, a call from "the bank", an OLX deal. These are chat inputs, not
      screens — but the engine has no recovery knowledge at all today, and the answer shape
      there is recovery steps rather than red flags.
- [ ] **Publish the first three to five Knowledge posts** in both reply languages, drawn from
      the same material.
- [ ] **Add the hardest cases** to `tests/fixtures/golden/checks.json` so detection quality
      cannot silently regress.
- [ ] **Reviewed `uz_latn`/`ru` wording** on the highest-traffic cards, and the first
      `exclude` entry — a legitimate bank SMS ("kod … hech kimga aytmang") currently trips
      `fs.secrecy.tell_nobody`.

## 7. The open question this plan does not answer

**Where the first few hundred users come from is undecided.** No surface in this roadmap
solves it, and it is a larger risk than any feature in it.

Two items work on it directly — the forwardable reminder (task 13) and family-group
behaviour (task 14), where one add reaches a whole family. Neither replaces a channel; they
amplify one once it exists.

This belongs on the founder's list before Phase 4 is reached, not after it.

## 8. Parked

Recorded so they are not rediscovered from scratch. Moving one into a phase requires an
explicit founder decision.

- **Avvalo Verify** — official-registry facts, specified in
  [VERIFY_VALIDATION.md](VERIFY_VALIDATION.md). Parked, not cancelled; the catalog it needs
  is being built anyway as lookalike detection.
- **URL reputation** — *removed, not parked.* The local blocklist lookup shipped disabled
  behind `URL_REPUTATION_ENABLED` with an empty domain list, so it changed no answer for its
  whole life. The module, the `url_blocklist` table (migration `0014`), the public-feed
  refresh job and the shipped domain file were deleted rather than carried further. Reviving
  it means rebuilding it against real material from the content track, with the lookalike
  catalog in `rules/shared/official_domains.yaml` as the starting point instead.
- **Linking a fired knowledge card to a published Knowledge post** — `reviewed_case_ids` is
  already threaded end to end and every baseline card sets it to `[]`. Two constraints if it
  is ever taken up: the validator strips every URL from model output, so the link must be
  appended deterministically in [app/engine/format.py](../app/engine/format.py) after
  validation; and Knowledge is web-only, so the bot has no surface for it.
- Cut during scope planning: digital-hygiene checklist · phishing trainer · personal counter
  · voice answers · third-party-addressed answers · result-as-image · Telegram account
  verification · on-device URL analyzer · PDF and voice input · clarifying dialogue ·
  "I'm on a call now" screen · rule-attribution display · home-screen install.

## 9. Not on the roadmap

- Avvalo Merchants; user-generated stories, comments, ratings, or accusation feeds.
- Person, phone, card, or handle lookup; authenticity verdicts; pattern classifiers or
  training on submissions.
- Fetching, rendering, or executing a submitted destination beyond PRODUCT_GUIDE §8.1.
- Autonomous browsing or reverse-image search.
- Bank, telco, marketplace, payment, escrow, or white-label integrations.
- Billing or a final revenue model.

These require a new founder decision backed by evidence, and must not be pulled into a task
because they appear in Git history or a superseded document.

## 10. Definition of roadmap complete

Phases 1–4 are live and verified in production; the catalog covers the top organizations;
real Uzbek material is encoded and covered by golden fixtures; recovery knowledge answers
the "it already happened" situations; Cyrillic-Uzbek output ships; the first Knowledge posts
are published; and a 14-day return rate has been recorded from real users rather than
estimated.
