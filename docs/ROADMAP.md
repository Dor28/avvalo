# Avvalo — Current Roadmap

> **Status:** Active order of work
> **Last updated:** 2026-07-22
> **Product authority:** [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md)

This roadmap contains one product path only. Founder-authored educational cases support discovery
and teach the checking habit, but do not create another product or reuse submitted checks.

## 0. Rules for every work session

1. Read [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) first.
2. Work on one phase and one acceptance boundary at a time.
3. Never persist or log submitted content.
4. Never output a verdict or score.
5. Never claim an official source was checked without a typed Avvalo Verify result.
6. Do not create an implementation task for a feature that has not passed its product gate.
7. `main` deploys to production; merge only with explicit founder authorization and passing
   automated checks.

## Editorial cases — Implemented, content rollout pending

- [x] Public trilingual list and individual case pages.
- [x] Founder-only login and trilingual draft/publish editor.
- [x] Editorial content stored separately from user-check data.
- [x] Published cases link readers back to the unified checker.
- [ ] Founder configures `ADMIN_ACCESS_KEY` in production.
- [ ] Founder writes, reviews, and publishes the first three to five cases in all language forms.

Cases are manually authored education. They are not Avvalo Verify evidence, a public allegation
database, public submissions, comments, ratings, or automatic derivatives of user checks.

## Phase A — Validate Avvalo Verify manually

Produce the packet in [VERIFY_VALIDATION.md](VERIFY_VALIDATION.md):

- [ ] 30 representative scenarios: 10 per MVP verification family.
- [ ] Founder-reviewed source inventory.
- [ ] Deterministic evidence wording in all three language forms.
- [ ] Advice-only and evidence-backed answer pair for every scenario.
- [ ] Paired user sessions with categorical results.
- [ ] Explicit `go`, `revise once`, or `stop` decision.

Gate for `go`: at least 40% decision-relevant evidence coverage, at least 70% preference for the
evidence-backed answer, and zero invented, overstated, unsourced, or person-level facts.

No feature code is part of Phase A.

## Phase B — Specify and build the strict MVP

This phase starts only after a recorded Phase A `go`.

Create one executor-ready task under `docs/tasks/`. It may cover only:

1. official identity match;
2. link and QR evidence;
3. regulated organization and license routing.

The task defines typed evidence, approved sources, refresh and failure behavior, privacy boundaries,
trilingual wording, adversarial tests, migrations if required, and rollout flags. It must not include
general web browsing or another product feature.

Implementation is complete only when focused tests, the full suite, Ruff, privacy/secret checks,
and human three-language review all pass.

## Phase C — Run the measured alpha

Recruit only after the MVP is audited and deployed.

- [ ] 60 activated users.
- [ ] 150 completed real checks.
- [ ] 30 users with a full 14-day return opportunity.
- [ ] At least 30 consented or supervised fact-quality audits.
- [ ] Metrics calculated exactly as defined in `VERIFY_VALIDATION.md`.
- [ ] Founder records `continue`, `revise once`, or `stop`.

The alpha passes only with at least 35% evidence coverage, at least 98% audited fact precision, zero
critical false facts, at least 70% evidence usefulness, at least 25% decision impact, complete
source/time attribution, and zero privacy incidents.

## Not on the roadmap

- Avvalo Merchants;
- user-generated stories, comments, ratings, accusation feeds, or aggregate trend feeds;
- voice, group monitoring, family accounts, or new product faces;
- pattern similarity, classifiers, or training on submissions;
- autonomous browsing, reverse-image search, or authenticity verdicts;
- bank, telco, marketplace, payment, escrow, or white-label integrations;
- billing or a final revenue model.

These items require a new founder decision backed by evidence. They must not be pulled into a task
because they appear in git history or a superseded document.

## Definition of roadmap complete

The roadmap is complete when the concierge gate passes, the strict three-family MVP is live and
audited, the measured alpha reaches its sample, and the founder makes a written decision from the
agreed metrics.
