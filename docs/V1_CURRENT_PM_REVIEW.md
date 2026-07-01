# Avvalo - Current Senior PM Review

> **Status:** Current product review and improvement backlog
> **Date:** 2026-06-30
> **Scope reviewed:** Product docs, v1 build docs, README, core engine/web/bot surfaces, tests, and deployment notes.
> **Purpose:** Identify the weakest product assumptions and documentation gaps before the IT Park demo, private alpha, or paid Seller Guard pilots.

## 0. Executive verdict

Avvalo has a strong product spine: the "check before you commit" frame is safer than the retired accusation-graph model, the output contract is disciplined, the shared engine is a good solo-founder architecture, and the Family Shield/Seller Guard split gives the project both mission and revenue logic.

The weak spot is not product imagination. The weak spot is **decision hygiene**: the docs now mix three different jobs into one v1 narrative.

1. **IT Park demo:** prove a credible localized platform with one engine, two faces, and web.
2. **Family Shield demand alpha:** prove ordinary users form a repeated "forward before acting" habit.
3. **Seller Guard revenue discovery:** prove merchants will pay for a verification workflow.

Those are all useful, but they are not the same test. A polished grant demo can still leave demand and revenue unproven. A green Family Shield alpha can still fail as a business if Seller Guard does not convert. A few merchant interviews can invalidate the build order faster than another month of engineering.

## 1. Current source-of-truth map

Use this map until the docs are reorganized:

| Artifact | Current role | PM note |
|---|---|---|
| `PRODUCT_GUIDE.md` | Strategic principles and safety authority | Still the top-level product guardrail. |
| `V1_BUILD_SCOPE.md` | Current demo build direction | Treat as the IT Park demo scope, not proof of validated demand. |
| `V1_TECHNICAL_PLAN.md` | Engineering contract for the demo/MVP surface | Strong, but several acceptance points now need tightening against implementation reality. |
| `FAMILY_SHIELD_VALIDATION.md` | Family Shield alpha contract | Still useful, but narrower than the current demo build and should be revised before real alpha recruitment. |
| `V1_MVP_PRODUCT_REVIEW.md` | Earlier Family Shield critique | Keep as background; many P0s were partially addressed by the build scope. |
| `FUNDABILITY_AND_GTM.md` | Historical fundraising/GTM thinking | Partly obsolete after the no-accusation/no-retention pivot. Do not pitch graph/data-infra claims from it. |

## 2. P0 weak spots

### P0.1 - Three north stars are competing

**Problem:** The product guide and Family Shield validation spec describe a narrow consumer alpha. The build scope and technical plan describe a grant-demo platform with Family Shield, Seller Guard, Telegram, and web. The README/docs index still partly describe earlier states.

**Why it matters:** The team can finish a large build and still not know which question was answered. Investors, grant panels, and alpha users need different evidence.

**Improvement:** Make the v1 narrative explicit:

- **Demo success:** one engine, two faces, two channels, safe outputs, no content persistence, working metrics export.
- **Demand success:** Family Shield cohort, activation, repeat/return behavior, usefulness, delayed outcome, safety/privacy gates.
- **Revenue success:** merchants accept a named price and commit to dated paid pilots.

### P0.2 - Fundability doc still carries the retired graph/data-infra thesis

**Problem:** `FUNDABILITY_AND_GTM.md` still talks about anti-fraud data infrastructure, graph-match rate, verified reports, and data acquisition. That conflicts with the current no-accusation, no-content-retention posture.

**Why it matters:** A pitch that implies a report graph or retained fraud database reopens the legal/product risk the pivot was meant to remove.

**Improvement:** Rewrite the fundraising story around:

- localized safety workflow engine;
- privacy-safe aggregate signals, not retained accusations;
- Seller Guard merchant workflow and eventual payment-provider confirmation;
- trusted Uzbek/Russian safety brand;
- on-prem/self-host roadmap for data residency.

### P0.3 - Seller Guard revenue is still not being tested hard enough

**Problem:** The docs correctly identify Seller Guard as the revenue hypothesis, but the current build explicitly excludes subscriptions, payment-provider integrations, team accounts, and real merchant workflows. That is fine for the demo, but not enough for business validation.

**Why it matters:** A beautiful merchant checker that no merchant pays for is a feature, not a business.

**Improvement:** Treat merchant discovery as a gate, not background work. Before or during the demo build, run structured interviews with a named price and a dated pilot ask. Three independent merchants accepting the price and pilot date should move Seller Guard ahead of more consumer work.

## 3. P1 weak spots

### P1.1 - Family Shield may validate the wrong user

**Problem:** The product names less digitally confident adults and families, but the actual flow requires someone to notice suspicion, open the bot, and forward content. The validation cohort allows too many founder-network/peer users, and the current v1 does not include family groups or guardian-dependent linking.

**Why it matters:** You may validate anxious, capable helpers while claiming you validated vulnerable end users.

**Improvement:** Before the alpha:

- make intended end users the majority of the measured cohort;
- report helper/peer metrics separately;
- add a simple "I am checking this for someone else" feedback dimension;
- avoid claiming the family-plan value prop is validated until a family-specific surface exists.

### P1.2 - Alpha metrics and demo metrics are mixed

**Problem:** The metrics export currently supports demo/pitch proof: checks, activation, completion, cost, no-signal rate, safety blocks. The Family Shield validation spec needs more: 14/30-day return behavior, decision impact, share intent, privacy incidents, p90 latency, delayed outcomes, and gate calculations.

**Why it matters:** Demo metrics show the system runs. Alpha metrics decide whether the product deserves more investment.

**Improvement:** Label the current export as **demo metrics** unless alpha-gate calculations are added. For the alpha, add:

- return within 30 days, not only 14-day repeat;
- delayed follow-up: "what actually happened after your check?";
- confirmed avoided payment or avoided data sharing;
- no-signal fire rate and false-negative review sample;
- p90 latency, not just average latency;
- privacy incident count.

### P1.3 - Provider/privacy posture is inconsistent

**Problem:** Older authority docs mandate local/on-prem OCR. Current build docs choose cloud OCR with DPA/zero-retention for the demo. That can be the right tradeoff, but it is not clearly recorded as a demo-stage exception.

**Why it matters:** Privacy is part of the product promise. Ambiguity here weakens trust and creates implementation churn.

**Improvement:** Add a provider decision record before public alpha:

- OCR provider, data region, DPA/no-retention setting, and whether images are used for training;
- LLM host/model, data retention/training policy, and fallback local path;
- counsel checkpoint before unsupervised users;
- production roadmap for on-prem OCR/self-hosted model if demand validates.

### P1.4 - Web consent and abuse controls need explicit acceptance

**Problem:** The review found that the web channel's privacy and abuse promises were more specific than the acceptance tests. In particular, the route must prove that consent is checked before content handling and that anonymous limits cannot be bypassed by simply clearing cookies.

**Why it matters:** The web channel is the easiest place to break the privacy promise or get abused.

**Improvement:** Keep these acceptance criteria locked:

- a no-consent web POST must not read image bytes, call Turnstile, call `run_check`, increment limits, or write events;
- decide whether v1 is session-only or IP-plus-session limited;
- test the over-limit path at the route level;
- clarify or add a web deletion/reset path for anonymous users.

## 4. P2 weak spots

### P2.1 - OCR acceptance is softer than the product promise

**Problem:** OCR providers and metadata stripping exist, but the test surface is not yet enough to prove the image promise under realistic Uzbek/Russian screenshots.

**Improvement:** Split acceptance into two layers:

- **Unit acceptance:** provider selection, EXIF/GPS stripping, low-confidence path, no LLM call on OCR failure.
- **Staging acceptance:** credentialed Cloud Vision smoke, Tesseract/local smoke, one image golden per language/script, and an operator note on OCR quality limits.

### P2.2 - Validator does not fully prove "rule hits are authoritative"

**Problem:** The docs say the LLM may not erase or invent rule hits. The validator blocks verdict words, raw contacts, unsafe instructions, and missing structure, but it does not fully verify that high-severity rule facts appear in the final explanation.

**Improvement:** Either de-scope this to "rules are passed as grounded prompt facts" or add tests that high-severity rule families appear in the output facts or fallback safely.

### P2.3 - README/docs status is stale

**Problem:** README and docs index still contain earlier "T1/later task" and "Family Shield next step" wording even though the repo now includes bot, engine, Seller Guard, web, metrics, hardening, and deployment surfaces.

**Improvement:** Update status language so new contributors know what exists, what still needs live-provider validation, and which docs are historical.

## 5. Recommended improvement backlog

### Do now, before more feature work

1. Update the docs index and README to reflect the current v1 shape.
2. Mark `FUNDABILITY_AND_GTM.md` as historical and rewrite the current pitch around Seller Guard workflow plus privacy-safe platform evidence.
3. Add a `docs/SELLER_GUARD_DISCOVERY.md` or appendix with interview script, price test, and pilot criteria.
4. Add web consent-order acceptance and route tests.
5. Decide and document whether anonymous web rate limiting is session-only or IP-plus-session.

### Do before IT Park demo

1. Run `tools/eval_models.py` against the intended hosted model and read the Uzbek outputs manually.
2. Run one credentialed OCR smoke on real Uzbek Latin, Uzbek Cyrillic, and Russian screenshots.
3. Export demo metrics and label them as demo metrics, not demand validation.
4. Prepare the pitch line: "demo-ready platform, revenue discovery in progress."
5. Show Seller Guard as a paid hypothesis, not as proven revenue.

### Do before Family Shield alpha

1. Revise `FAMILY_SHIELD_VALIDATION.md` so the cohort is mostly intended users.
2. Add delayed outcome follow-up and confirmed avoided-payment/data-sharing metrics.
3. Add no-signal false-negative sampling.
4. Record the cloud OCR/LLM legal/provider decision.
5. Get local lawyer review for privacy notice, operator identity, and foreign processing.

### Do before Seller Guard paid pilot

1. Interview at least 20 merchants across Telegram/Instagram shops, delivery-heavy sellers, and high-ticket informal sellers.
2. Use a named monthly price in every late interview.
3. Ask for a dated paid pilot, not vague interest.
4. Record current workaround, frequency of suspicious orders, value of one avoided loss, and who can approve payment.
5. Treat three independent named-price pilot commitments as the revenue signal to prioritize Seller Guard.

## 6. Merchant discovery instrument

Use this as the first version of the Seller Guard interview script.

### Target segments

- Telegram/Instagram shops with daily order volume.
- Sellers of electronics, cosmetics, clothing, and other courier-delivered goods.
- Sellers who accept card transfer screenshots or courier handoff proof.
- Small teams where the owner personally reviews suspicious orders.

### Interview questions

1. How many orders do you handle per week?
2. How often do customers send payment screenshots before you see money in the bank app?
3. What suspicious buyer patterns did you see in the last 30 days?
4. What was the most expensive fake-payment, courier, refund, or chargeback incident?
5. How do you currently verify payment before giving goods to courier/customer?
6. Who on the team is allowed to decide "do not release the goods yet"?
7. If a Telegram assistant turned a screenshot/chat into a verification checklist, when would you use it?
8. What would make the result trustworthy enough for staff to follow?
9. At `X` sum per month, would you start a paid pilot on a specific date?
10. If yes, what date, who signs off, and what result would make you continue paying?

### Pass/fail criteria

- **Strong signal:** at least three independent merchants accept a named monthly price and commit to a dated paid pilot.
- **Medium signal:** merchants report frequent pain and request a trial, but avoid price commitment.
- **Weak signal:** merchants call it interesting but say they already trust bank-app checks or would not pay.
- **Stop/pivot signal:** pain is rare, losses are small, or the buyer of the tool is unclear.

## 7. Positioning guardrails

Use these lines consistently:

- Avvalo verifies the **situation/process**, not a person's reputation.
- Avvalo does **not** certify safety and does **not** call anyone a scammer.
- Family Shield is the community wedge and trust surface.
- Seller Guard is the revenue hypothesis.
- The current v1 can be demo-ready before the business is validated.
- Payment-provider API confirmation is the future moat for Seller Guard; screenshot analysis alone is not.
- Privacy-safe aggregate metrics are allowed; retained accusation data is not.

## 8. PM decision needed

Before the next product milestone, choose one primary objective:

1. **Grant objective:** finish the demo, tighten docs, and collect enough usage/merchant quotes for IT Park.
2. **Revenue objective:** pause broad polish and push Seller Guard discovery until paid-pilot evidence appears.
3. **Demand objective:** run the Family Shield alpha and accept that revenue remains unproven.

My recommendation: **Grant objective plus revenue discovery.** Finish the demo because the build is already near that shape, but make Seller Guard interviews a hard weekly gate. Do not interpret grant-demo readiness as proof of product-market fit.
