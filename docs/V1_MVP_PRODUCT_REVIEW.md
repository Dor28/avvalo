# Avvalo — Deep Product Review of the v1 MVP

> **Status:** Critical review (pre-build) · 2026-06-24
> **Scope reviewed:** The **Family Shield validation build** — the locked v1 MVP — as specified in [FAMILY_SHIELD_VALIDATION.md](FAMILY_SHIELD_VALIDATION.md), framed by [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) and the engine reference in [PRODUCT_DESIGN.md](PRODUCT_DESIGN.md).
> **Voice:** Brutally honest senior-PM pass. Findings are rated 🔴 High / 🟡 Medium / 🟢 Low. The goal is a *better experiment*, not a longer one.
> **What "v1" means here:** Per the authoritative docs, v1 is **not** the three-product portfolio and **not** the accusation-graph design — both are superseded. v1 is the single one-behaviour Family Shield micro-MVP and its 21-day private alpha.

---

## 0. Verdict (bottom line up front)

**The MVP is unusually well-specified and safe — and that is also its risk.** The safety posture, privacy/retention design, and the quantified go/pivot/stop gates are stronger than 95% of seed-stage specs. The spec's discipline is real and should be protected.

But the experiment as written is **over-engineered on the parts that don't reduce demand risk, and under-specified on the parts that do.** Specifically:

- The build bets on the **single hardest technical component** (local Uzbek/Cyrillic OCR) for a legal reason that your own pivot doc says was *relaxed* — adding weeks of build risk to a demand experiment.
- The headline success metric (**25% 14-day repeat use**) is mis-calibrated to the real-world base rate of "forward-worthy" scam encounters, so a good product can fail the gate for reasons unrelated to quality.
- The **recruited cohort** is biased toward people who least resemble the intended end user, so a green result may not mean what it claims.
- The two features that decide whether the output is *trustworthy and useful* — the **"no warning signs" path** and the **safety output-validator** — are the least designed in the doc.
- The stated emotional value prop ("**help me protect my mom**") has **no product surface** in v1.

None of these are fatal. All are fixable before recruiting. The single biggest strategic question is whether Family Shield should be the build at all when your own analysis says **Seller Guard is the only product with a payer** — addressed in §7.

**Recommendation in one line:** Ship a *thinner, cheaper, faster-to-build* version of this exact experiment (cloud OCR + cheap model, recalibrated metrics, two designed-for paths), and run merchant interviews in parallel as the real revenue probe.

---

## 1. What v1 actually is — feature inventory

So the review is anchored to concrete features, here is the full MVP surface (from [FAMILY_SHIELD_VALIDATION.md](FAMILY_SHIELD_VALIDATION.md) §3–§9):

| # | MVP feature | What it does |
|---|---|---|
| F1 | **One entry flow** | `/start` → language → consent → single "forward a suspicious message" prompt. No category chooser. |
| F2 | **Multi-input intake** | Forwarded text, pasted text, one image ≤10 MB, optional caption. |
| F3 | **Local OCR** | On-prem OCR for images (UZ-Latin, UZ-Cyrillic, RU). Raw image never leaves. |
| F4 | **PII minimization** | Strip/minimize names, phones, cards, usernames, emails, addresses before any LLM call. |
| F5 | **Deterministic rule layer** | 7 rule families (§8) detect the 5 launch patterns independent of the LLM. |
| F6 | **LLM explanation** | Writes the output in UZ/RU, constrained to a fixed contract. |
| F7 | **Fixed output contract** | 🚩 red flags · manipulation pattern · ✅ verify · ❓ ask · limitation line. Never a verdict. |
| F8 | **"No warning signs" path** | Mandatory non-reassuring template when nothing fires. |
| F9 | **Output safety validator** | Checks the draft against prohibited-output rules before sending. |
| F10 | **Categorical feedback** | "Was this useful?" + "What will you do next?" — one tap each. |
| F11 | **Share button** | Bot link + promise only; never the user's content. |
| F12 | **Privacy-safe analytics** | Events with no content; cost/latency/token instrumentation. |
| F13 | **Privacy/retention controls** | `/privacy`, `/delete_my_data`, hard TTLs, no content in logs/backups. |
| F14 | **Limits & failure handling** | 5 checks/user/day; low-OCR, timeout, unsupported-media, danger paths. |

The five detection patterns (F5): fake bank support, family-emergency impersonation, seller prepayment, fake delivery link/QR, upfront-fee job offer.

---

## 2. What is genuinely strong (protect these)

A fair review names what not to break:

- **Safety-first output contract (F7/F8/F9).** "Verify the situation, never the person," no score, no "safe/scammer," the mandatory limitation line, and the non-reassuring empty-state template are the right design and the project's strongest asset. This is what makes the product *defensible and shippable* in a market with criminal defamation exposure.
- **Privacy/retention spec (F13).** The retention table — hard 1-hour TTLs on content, deletion that reaches logs/queues/caches/backups, pseudonymous HMAC user key, no content in analytics — is rigorous enough to be a **trust differentiator**, not just compliance. Most teams hand-wave this.
- **Hybrid rule + LLM engine (F5/F6).** Deterministic floor + LLM nuance is the correct architecture: the obvious signals can never be missed on an LLM's bad day, and rules are editable config.
- **Golden examples as acceptance fixtures (§7).** Five frozen input→output pairs as test fixtures is excellent engineering practice and forces the quality bar to be concrete.
- **Quantified go/pivot/stop gates (§12) + commercial override.** Pre-committed thresholds (and "3 merchants commit → pivot to Seller Guard") prevent the usual founder self-deception of an endless beta.

Keep all of the above. Everything below is about making the experiment *valid and cheaper*, or about quality gaps inside these features.

---

## 3. Deep findings

### A. The wedge & the behavioural model

**A1 🔴 The prevention paradox is unaddressed: the people who most need it are the ones who won't forward.**
The whole product depends on the user *recognising a message as suspicious enough to forward.* But the stated target — "less digitally confident adults" — are precisely the people who **don't feel the suspicion**; they act because they're convinced the message is real. By the time someone thinks "let me check this," they're already half-protected. The product captures the *anxious-but-capable* middle, not the *vulnerable* tail it's named for. The spec never confronts this. → **You are likely validating demand from worried, savvy users, then attributing it to protection of the vulnerable.** Decide which user you're actually serving and recruit/measure for *that* one.

**A2 🔴 The "help me protect my relative" value prop has no product surface in v1.**
[PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) §7 and [ADJACENT_PRODUCT_IDEAS.md](ADJACENT_PRODUCT_IDEAS.md) §2 sell the *emotional* value as "buying a safer way to help your parents." But v1 explicitly excludes family groups, shared accounts, and any guardian↔dependent link (§3 out-of-scope). So the protective-relative scenario reduces to "the relative also uses the bot for themselves." **The most differentiated, most defensible, most emotionally sticky version of Family Shield is not in the experiment.** That may be a deliberate scope cut — but then the alpha cannot claim to validate that value prop, and §11's "check for a family member" framing is measuring something the product doesn't actually support. Either (a) add a minimal "forward on behalf of someone" framing and measure it, or (b) drop the family narrative from the hypothesis and validate the honest thing: *a personal, in-language scam second-opinion bot.*

**A3 🟡 v1's value over a static PSA is thin — and that is exactly what the experiment must prove.**
Read the five golden outputs honestly: they are excellent, but they're the *same advice a one-page "how to avoid scams" poster gives* — don't share OTP, don't prepay, verify via the official app, don't open the link. The differentiation is delivery: **instant, conversational, in the user's exact language/script, grounded in their specific message.** That genuinely can beat a poster. But it also means the retention risk is structural: a user may "learn the lesson once" and not return. The doc's own admission that the rule DB "is not a moat" applies double here. → Frame the alpha's true question precisely: *does grounded, instant, in-language delivery form a habit that a static guide cannot?* If yes, you have something. If users treat it as one-time education, repeat use dies — and that's the real signal, not a metric to rescue.

### B. Cohort & measurement validity

**B1 🔴 The 25% / 14-day repeat-use gate fights the base rate of scam encounters.**
An individual consumer encounters a genuinely *forward-worthy* novel scam maybe once or twice a month, often less. Demanding that **25% of users hit a second real check inside 14 days** may be asking the population to encounter scams faster than scams actually arrive. A high-quality product can miss this gate purely on event scarcity — or the cohort games it with synthetic/curiosity checks (which §2 says to exclude, shrinking the sample further). The *instinct* (habit > curiosity) is right; the *threshold and window* are likely miscalibrated. → Either lengthen the window (e.g. 30 days), lower the bar, or replace "repeat within 14 days" with a leading indicator better matched to a rare trigger — e.g. **"saved/pinned the bot," "returned at all," or stated intent-to-reuse** combined with a longer passive observation tail.

**B2 🔴 The cohort is recruited from the population least like the target user.**
60–100 people from "founder networks and trusted communities," only **≥1/3 intended end users**. The other ~two-thirds (tech/startup peers) will *inflate* activation and usefulness and *deflate* realism. Meanwhile the intended end-users (less digitally confident adults) are the hardest to recruit through a technical founder's network and the hardest to onboard to a Telegram bot — so the validity of the entire demand read rests on the smallest, hardest-to-reach third. → Flip the ratio: make intended end-users the **majority** of the measured cohort, report their metrics **separately** from peers, and treat the peer numbers as a smoke test only, not as demand evidence.

**B3 🟡 No baseline / control — "25% repeat in a primed cohort" ≠ organic pull.**
Every participant is recruited, told what it is, and motivated to help the founder. There's no comparison against the status quo (ask a savvy relative, Google it, ignore it). Absolute repeat-use in a primed cohort systematically overstates organic demand. A full control arm is unrealistic solo, but the report should at least **caveat the priming bias explicitly** and weight a small number of *cold* (un-coached, organically referred) users heavily — they're worth 10 coached ones.

**B4 🟡 Decision-impact is self-reported intent measured at peak fear.**
"Decision impact ≥ 20%" rests on the one-tap "what will you do next?" asked *immediately after a scary read* — biased hard toward the socially-desirable "verify independently." Intent ≠ behaviour, and the strongest real-impact metric from the older spec ("**confirmed they avoided a payment**", [PRODUCT_DESIGN.md](PRODUCT_DESIGN.md) §13) was dropped. → Add a lightweight **delayed follow-up** to a subset ("last week you checked a message — what actually happened?"). One confirmed averted payment is worth more than 50 "I'll verify" taps, both for the gate and for any future fundraising line.

### C. Output quality — the two paths that decide trust

**C1 🔴 The "no clear warning signs" path is the single biggest quality-and-liability risk, and it's barely designed.**
With only **5 rule families** running over **PII-minimized** text, F8 will fire more often than the spec seems to assume — including on *sophisticated scams the rules miss.* When it does, the user reads "No clear warning signs were found" and, despite the disclaimer, **feels reassured** — the exact false-comfort failure the whole product exists to avoid. The disclaimer protects you legally; it does not protect the user psychologically, and it guts the value prop ("I asked for help and got a shrug"). → This path needs as much design as the positive path: (a) measure its **fire-rate** in the alpha as a first-class metric; (b) when it fires, still surface the **category-generic** verification questions confidently (don't let "nothing found" read as "nothing to do"); (c) audit a sample of "no warning signs" outputs against the *original* (pre-minimization) content to estimate the **false-negative rate** — that number, not usefulness, is the real safety signal.

**C2 🔴 The output safety-validator (F9) is asserted, not specified — and it's the safety-critical component.**
"Validate the draft against the prohibited-output rules in §6" is a one-liner, but it gates a rule where **one critical violation pauses the alpha.** A keyword filter catches "safe"/"scammer," but most prohibited items are *semantic*: inventing an "official" bank phone number, implying safety by tone, claiming Avvalo "checked" a database it didn't, instructing the user down the suspicious contact path. Step 6 even admits the risk ("do not invent emergency contacts") without giving a control. → Specify the validator concretely: deterministic checks for verdict-words + any phone/URL/credential *appearing in the output that wasn't in the rule layer's grounded facts* (catch hallucinated contacts), plus an LLM-as-judge second pass on a sample. Decide the **fail-action** (block + retry vs. block + generic fallback). This is the highest-leverage unspecified piece in the build.

**C3 🟡 Manipulation-pattern naming risks over-confident pattern-matching.**
F7 includes "a short explanation of the manipulation pattern when one is recognizable." Good for education — but if the LLM names a pattern the message doesn't actually fit (because rules half-matched on minimized text), you've manufactured a confident-sounding read on weak evidence. Keep the pattern line **strictly gated on rule hits**, never LLM-invented (§8 already says the LLM "may not invent" a rule hit — make sure the *pattern label* obeys the same gate).

### D. Privacy-vs-analysis tension (the hidden one)

**D1 🔴 PII minimization (F4) can strip the very signals the golden examples reason about.**
Several scam tells *live inside the identifiers you minimize:* a **lookalike domain** (Example 4 reasons explicitly about the link), a **"new number"** (Example 2), a card going to a **personal** account, a Telegram handle that mismatches a display name. If you raw-strip URLs/usernames/numbers *before* the LLM, the LLM cannot explain those flags — yet the golden outputs assume it can. This is a genuine, unreconciled tension between F4 and F5/F7. → Resolve it explicitly: minimize the **value** but preserve the **structure/signal** as a rule-layer token, e.g. `[LINK: shortened/lookalike domain]`, `[PHONE: claimed-new number]`, `[CARD: personal-account transfer]`. The rule layer (which sees the raw text locally, pre-minimization) is the right place to extract these signals and pass them to the LLM as grounded facts — so privacy and analysis depth stop fighting.

**D2 🟡 Clarify whether URLs/domains are "direct identifiers."** §3/§4 lists what's minimized but is silent on URLs and domains specifically. Given Example 4 depends on them, the spec must say *how* a link is represented to the LLM after minimization. Don't leave this to the implementer.

### E. Technical feasibility & cost

**E1 🔴 Local Uzbek/Cyrillic OCR is the hardest piece — and you may not need it for the alpha.**
Per your own memory note, **OCR has no public Uzbek benchmark** and the best/cheapest Uzbek text quality today is **cloud (Gemini Flash)** — which the spec forbids in favour of local OCR. Local OCR on UZ-Latin + UZ-Cyrillic + RU, on low-quality screenshots with stylised fonts, is genuinely hard and is the most likely source of *quality failures that look like demand failures.* Worse, the legal driver for "local OCR" was **relaxed on 27 Mar 2026** ([SESSION_DECISIONS.md](SESSION_DECISIONS.md), 2026-06-21 entry: foreign LLM/OCR now compliant via adequacy/SCCs) — yet the guide and validation spec still mandate local OCR "out of caution." **For a demand experiment, betting the build on the hardest infra component for a legal reason that was just softened is the wrong trade.** → Strongly consider **cloud OCR with a proper DPA + zero-retention config for the alpha**, behind the same consent notice, and defer local OCR to the production build *if* demand validates. This likely removes the single biggest schedule risk. (If counsel insists on local for the alpha, then OCR quality must be a tracked gate, because it will silently cap usefulness.)

**E2 🟡 The $0.03 cost ceiling effectively pre-selects a cheap model — say so, and check the math.**
Blended ≤ $0.015 target / $0.03 hard ceiling, *including local OCR compute*, is achievable only with a **Flash-tier** model, not a frontier model — and that model must still handle three scripts and produce the careful, safety-constrained output the golden examples demand. The spec names no model, leaving a latent conflict between the **quality bar** (§7) and the **cost bar** (§10). Also, folding **local GPU/OCR compute** into a $0.015 number is hand-wavy — idle GPU time isn't free and amortises badly at alpha volumes. → Name the candidate model(s) (your stack note points at Gemini Flash), run a 50-check cost spike *before* committing the ceiling, and report OCR compute as a **separate line**, not buried in the blended number.

**E3 🟢 The $100 alpha spend cap can throttle your best signal.**
At $0.03/check, $100 = ~3,300 checks — generous for the 150-check minimum, but **below max engagement** (100 users × 5/day × 21 days ≈ 10,500 possible). If the product is genuinely sticky, you hit the cap and "pause paid processing," suppressing the engagement you're trying to measure. → Fine as a guardrail, but pre-authorize a higher ceiling that triggers *automatically on a strong-engagement signal* so success doesn't get rate-limited.

### F. Language, script & onboarding

**F1 🟡 Code-switching and content-vs-UI language are unhandled.**
Uzbek users routinely mix RU and UZ (and Latin/Cyrillic) *in a single message.* The spec says "reply in the selected language; don't mix scripts unless quoting" — but (a) detection on code-switched text is error-prone, and (b) the user picks a UI language at consent, while their *forwarded content* may be in a different language. Which wins for the reply? Unspecified. Wrong-language replies are an instant UX break for exactly the less-confident users you care about. → Define the precedence rule (recommend: reply in the *content's* dominant language, fall back to UI choice) and add code-switched fixtures to the test set in §13.6.

**F2 🟡 Onboarding friction will dominate the activation metric for the target user.**
Find-bot → /start → read consent → pick language → forward a message is a lot for a less-digitally-confident adult. The activation-rate metric (§11) will conflate "couldn't onboard" with "didn't want it." → Run the §13.7 supervised usability test **specifically with intended end-users (not peers)**, and instrument *where* in the funnel they drop, so a low activation number is diagnosable rather than ambiguous.

---

## 4. Feature-by-feature scorecard

| Feature | Verdict | Note |
|---|---|---|
| F1 One entry flow | ✅ Keep | The "one behaviour" discipline is correct. |
| F2 Multi-input intake | ✅ Keep | |
| F3 Local OCR | ⚠️ **Reconsider for alpha** | E1 — biggest build risk; cloud OCR + DPA likely sufficient for the experiment. |
| F4 PII minimization | ⚠️ **Redesign** | D1/D2 — preserve signal structure, not just strip values. |
| F5 Rule layer (7 families) | ✅ Keep + extend | Add link/number *structure* extraction (D1). |
| F6 LLM explanation | ✅ Keep | Pin the model against the cost ceiling (E2). |
| F7 Output contract | ✅ Keep | Gate the pattern label on rule hits (C3). |
| F8 "No warning signs" path | 🔴 **Design properly** | C1 — measure fire-rate + false-negative rate. |
| F9 Safety validator | 🔴 **Specify** | C2 — the safety-critical, under-specified piece. |
| F10 Categorical feedback | ✅ Keep + add follow-up | B4 — add a delayed behaviour check. |
| F11 Share button | ✅ Keep | Directional metric only, as stated. |
| F12 Privacy-safe analytics | ✅ Keep | Add: OCR-confidence, "no-warning-signs" fire-rate. |
| F13 Privacy/retention | ✅ Keep | Best-in-class; protect it. |
| F14 Limits & failure | ✅ Keep | Make the spend cap success-aware (E3). |

No feature should be **cut**. The changes are: redesign two (F4, F8), specify one (F9), reconsider the implementation of one (F3), and instrument three better (F8, F10, F12).

---

## 5. What's missing from v1 entirely

Gaps not represented by any feature above:

- **A false-negative / OCR-quality observability loop.** The spec measures usefulness and safety *pass* rate, but has no first-class measure of **what the product missed** (scams the rules didn't catch, text the OCR garbled). Without it, "95% safety pass" can coexist with a high silent miss rate. → Add false-negative sampling to the §11 quality audit.
- **A designed answer to "why come back."** No re-engagement hook beyond the user spontaneously encountering another scam. Even within scope (no content retention, no alerts), a *weekly one-line "new scam going around" nudge* — authored, not data-derived — would directly test whether a habit can be *seeded* rather than waited for. Currently retention is left entirely to chance + scam base rate (see B1).
- **A defined precedence for content-language vs UI-language** (F1 above).
- **A concrete merchant-interview instrument.** §12's commercial override is the most important escape hatch in the whole plan (it can flip the company to its only product with a payer), yet "10 structured merchant interviews" has no script, no named-price test, no pilot-commitment template. This deserves the same rigor as the consumer gates — see §7.

---

## 6. The two-paragraph risk summary for a busy founder

The experiment is *safe* and *well-instrumented* but **slow to build and possibly mis-aimed.** The build cost is concentrated in local OCR (hardest component, weakened legal rationale), while the demand read is weakened by a base-rate-fighting repeat metric and a cohort skewed away from the real user. The two features that determine whether users *trust* the output — the empty-state path and the safety validator — are the least designed. And the emotional pitch (protect my family) isn't actually in the product.

Fix order: (1) recalibrate the metric and cohort so a green result *means something*; (2) specify the safety validator and the "no warning signs" path so quality is real; (3) swap local OCR for cloud-with-DPA to cut weeks off the build; (4) reconcile PII minimization with analysis depth. Do those four and you have a fast, honest experiment. Then the only question left is the strategic one.

---

## 7. The strategic question: is Family Shield even the right v1?

This must be said plainly, because your own documents keep circling it:

- [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) §8 states Seller Guard is "the only idea with all four of **payer + frequency + ROI + retention**."
- §7 admits Family Shield's payer (telco/bank sponsorship or family plan) is an **unproven, slow** hypothesis.
- §12 of the validation spec includes a **commercial override**: if 3 merchants commit to a paid pilot, pivot to Seller Guard *even if Family Shield is green.*

Put together, that is the doc quietly admitting: **the consumer experiment can succeed and still not matter, because the revenue lives elsewhere.** The justification for building Family Shield first (cheap reach, brand, seeds patterns) is reasonable — but the *cheapest possible* test of the thing that actually matters (will merchants pay?) is **merchant interviews, which cost $0 of build time** and are already in the plan as a "parallel" afterthought.

**Honest framing of the choice:**

| Path | Build cost | What it proves | Risk |
|---|---|---|---|
| **A. Family Shield-first** (current plan) | 2–4 wk build + 21-day alpha | Consumers form a free habit | Validates the product with **no proven payer**; defers revenue |
| **B. Seller Guard micro-MVP first** | Similar build, narrower | Merchants get value on a recurring pain | Harder cold-start (fewer users), but tests the **only payer** |
| **C. Interviews-first, build second** | Days, ~$0 | Whether *anyone* will pay, before any build | Cheapest information; doesn't prove the product works |

**Recommendation:** Don't treat the merchant track as "parallel, non-engineering." Treat **Path C as a gating pre-step**: run the 10 merchant interviews *with a named price and a dated-pilot ask* **before or during** the first two weeks of the Family Shield build. If three merchants commit, you've learned the most important fact in the company for the price of ten conversations, and the build effort should follow the money (Path B). If they don't, Family Shield-first is the right hedge and you proceed — now with that question actually answered rather than deferred. Either way, **the merchant-interview instrument deserves the same rigor as the consumer gates**, and it currently has none.

---

## 8. Prioritized recommendations

**P0 — do before recruiting the alpha cohort:**
1. **Specify the safety output-validator (F9)** with deterministic + judge checks and a defined fail-action (C2). Safety-critical.
2. **Design and instrument the "no warning signs" path (F8)** — fire-rate + false-negative sampling (C1).
3. **Reconcile PII minimization with analysis depth (F4)** — preserve signal structure as rule-layer tokens (D1/D2).
4. **Recalibrate the repeat-use gate and window** to the real scam base rate; report intended-end-users separately and as the majority (B1/B2).
5. **Decide OCR for the alpha** — default to cloud + DPA + zero-retention unless counsel insists otherwise (E1).

**P1 — do during the build:**
6. Pin the LLM model and run a 50-check **cost spike** against the $0.03 ceiling; report OCR compute separately (E2).
7. Add a **delayed behaviour follow-up** to a feedback subset (B4) and **false-negative sampling** to the weekly audit (§5).
8. Define **content-vs-UI language precedence** and add code-switched fixtures (F1).
9. Make the **$100 spend cap success-aware** (E3).

**P1 — strategic, in parallel from day one:**
10. Run the **10 merchant interviews with a named price + dated-pilot ask** as a *gating* pre-step, not an afterthought; build the interview instrument with the same rigor as the consumer gates (§7).

**Consider (P2):**
11. Add a minimal **"forward on behalf of a relative"** framing so the alpha actually tests the family value prop — or drop the family narrative from the hypothesis (A2).
12. Add an authored **weekly "scam going around" nudge** to test seeded (not waited-for) re-engagement (§5).

---

## 9. Open questions for the founder

1. **Who is the v1 user — really?** The anxious-but-capable forwarder, or the vulnerable relative? They need different cohorts, metrics, and possibly different products (A1/A2).
2. **Is local OCR a hard legal requirement for the alpha, per actual counsel — or caution?** This single answer changes the build timeline by weeks (E1).
3. **What repeat-use rate is realistic given how often *your* target users actually meet a forward-worthy scam?** If you don't know, that's the first thing to learn from the supervised test (B1).
4. **Will you let merchant evidence gate the build, or only the post-alpha decision?** §12 says it *can* override even a green result — so why wait 5 weeks to ask them? (§7).
5. **What is the acceptable false-negative rate**, and how will you know you're under it when content isn't retained? (C1/§5).

---

*Cross-references: [FAMILY_SHIELD_VALIDATION.md](FAMILY_SHIELD_VALIDATION.md) (the spec under review) · [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) (direction) · [PRODUCT_DESIGN.md](PRODUCT_DESIGN.md) (engine reference) · [SESSION_DECISIONS.md](SESSION_DECISIONS.md) (the 2026-06-21 pivot & localization update).*
