# Avvalo — Product Vision: Check · Learn · Share

> **Status:** Senior-PM vision & recommendation · 2026-07-04
> **Owner:** Solo technical founder (Uzbekistan)
> **Why this doc exists:** the founder asked to re-anchor the product after the June build sprint — "what did we actually build, how does it relate to the original design, and what should the platform become?" This is my opinionated answer. Safety rules from [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) still win on any conflict.
> **Reads with:** [V1_CURRENT_PM_REVIEW.md](V1_CURRENT_PM_REVIEW.md) (execution backlog), [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) (principles), [PRODUCT_HORIZONS.md](PRODUCT_HORIZONS.md) (the 3-year option map beyond this plan), [archive/PRODUCT_DESIGN.md](archive/PRODUCT_DESIGN.md) (the original graph-era spec).

Legend: ✅ built & tested · 🔨 build next · 🔶 hypothesis · ❌ do not build

---

## 1. Clearing the confusion: three eras, one product

You remember the product as [archive/PRODUCT_DESIGN.md](archive/PRODUCT_DESIGN.md) described it. The repo contains something different. Neither is a mistake — there were two deliberate turns, and it helps to see all three eras side by side:

| | Era 1 — original design (2026-06-20) | Era 2 — the pivot (2026-06-21) | Era 3 — what is in the repo today |
|---|---|---|---|
| Core idea | AI check + **silent accusation graph** ("this card was reported 3×") | **"Verify the situation, not the person"** — no accusation database | One engine, two faces (Avvalo + Merchants), Telegram + web |
| The data asset | Graph of phones/handles/cards tied to scammers | Opt-in, de-identified pattern examples (later) | Privacy-safe aggregate metrics only (`check_event`: which rule families fired, language, cost — **zero content stored**) |
| Why it changed | — | Legal review: defamation is **criminal** in UZ (Art. 139/140), operator bears the burden of proving accusations true; weak lawful basis for processing the accused's data | Build scope aimed at the IT Park grant demo (2026-06-24) |
| Status | Retired (background reference) | Authoritative principles | **Built, tested, deployable** |

**What is actually built (verified against the code today):** the full check pipeline (intake → OCR → PII minimization → deterministic rules → LLM → safety validator → fixed 🚩/✅/❓ output), a working Telegram bot (@Avvalo_official_bot) with consent/privacy/deletion flows, an anonymous web app (family + `/merchants` pages), 11 consumer + 5 merchant rule families, three language forms (UZ-Latin, UZ-Cyrillic, RU), OCR via Cloud Vision / Tesseract / PaddleOCR, per-user daily limits, retention TTLs, a metrics export, Docker prod stack, CI, and ~27 test modules. **Not built:** payments, accounts, any person-lookup, any content/community surface, alerts.

So: the *engine* from the original design survived almost intact. What was cut is the accusation graph — and that cut stays. What was never started is the part you're now asking about: **the layer that attracts, teaches, and retains people.**

---

## 2. What you asked for — and my honest verdict on each

You said: *"self-improvement platform that helps regular people find fraud — articles, checkers, maybe forum with stories — just help people — then maybe a startup that takes investment with the data I collected."*

First, one reframe. "Self-improvement platform" is the wrong label — that category means habits/productivity apps and will confuse everyone. What you actually described is a **digital-safety platform**: people come to *check*, stay to *learn*, and contribute by *sharing what happened to them*. That is a coherent, buildable, fundable product. Keep the mission sentence: **"Avvalo helps ordinary people in Uzbekistan not get scammed."**

My verdict on each piece:

| Your ask | Verdict | Reasoning |
|---|---|---|
| **Checkers** | ✅ Done — ship it | The engine is the hardest part and it exists. Everything below feeds it users. |
| **Articles** | 🔨 Yes — build this next | Cheapest, highest-leverage missing piece. There is no good UZ-language scam-awareness hub. Every article is SEO + trust + a funnel into the bot. And you already have the skeleton: the 11 rule families in `rules/family/families.yaml` *are* the table of contents. |
| **Forum with stories** | 🔶 Yes to **stories**, ❌ no to an **open forum** (for now) | Stories are the emotional hook and the retention engine — right instinct. But an open forum on day 1 is (a) empty (cold-start), (b) a moderation job you don't have time for, and (c) the defamation surface the pivot removed — users *will* post names, phones, and cards. Start with **curated stories**: opt-in capture after a check → PII stripped → you review → published. A Telegram channel with comments enabled is your "forum v0" for free. |
| **"Investment on the data I collected"** | 🔶 Yes — but only the legal version | The accusation graph is not coming back; in Uzbekistan that dataset is a criminal-liability generator, not an asset. But you are **already collecting** a legal data asset and may not have noticed: every check records *which scam-pattern families fired, in which language, on which face, at what cost* — aggregate trend intelligence with zero personal data. Add opt-in de-identified stories and a labeled UZ/RU scam corpus on top, and you have a real, defensible, *sellable-in-aggregate* dataset. §6 explains how to pitch it. |

---

## 3. The vision — one engine, three surfaces, one paid track

> **Avvalo is where Uzbekistan checks before it pays.**
> **Check** anything suspicious in seconds · **Learn** how each scam works · **Share** your story so the next person doesn't fall for it.
> Merchants pay for the professional version of the same engine.

```
                        ┌────────────────────────────┐
        CHECK ✅        │                            │      LEARN 🔨
  Telegram bot + web ──▶│      THE SHARED ENGINE      │◀── Scam library (articles)
  🚩/✅/❓ in UZ/RU      │  OCR → minimize → rules →   │    Weekly digest channel
                        │  LLM → validate → format    │    Monthly "Scam Pulse"
        SHARE 🔨        │                            │
  Opt-in stories ──────▶│  feeds: rule tuning +      │      MERCHANTS 🔶 (the payer)
  curated & redacted    │  aggregate trend data      │    subscriptions, gated on
                        └────────────────────────────┘    interview evidence
```

**Check** — the utility. Built. It answers "is this suspicious?" in the moment of fear. Its weakness is retention (people check when scared, then forget) — which is exactly what the next two surfaces fix.

**Learn** — the reach. A public scam library (one page per scam family: how it works, red flags, what to do, a real story, "check yours now" button), a weekly Telegram digest ("scam of the week"), and a monthly **Avvalo Scam Pulse** — "the top 5 scam patterns circulating in Uzbekistan this month," generated from your own aggregate check data. The Pulse is your PR engine: media quote it, banks notice it, and no competitor can write it without your traffic.

**Share** — the soul and the moat-adjacent asset. After a useful check: *"Did this help? Want to share what happened — anonymously — to warn others?"* Opt-in, auto-redacted by the existing minimizer, reviewed by you, published to the channel and the relevant library page. Stories describe **what happened and how the scam worked — never who did it**. Each story is content, proof of impact ("Avvalo saved me 2M soum"), and a labeled training example.

**Merchants** — the money. Unchanged from the current plan and deliberately *not* part of the community brand: the same engine sold as a work tool. The [V1_CURRENT_PM_REVIEW.md](V1_CURRENT_PM_REVIEW.md) gate stands — 20 interviews, a named price, three dated paid-pilot commitments before building billing.

**The flywheel:** someone gets a suspicious message → checks it → opts in to share the story → you publish it → readers follow the channel and learn → they check when their moment comes → aggregate patterns sharpen the rules and fill the Pulse → the Pulse builds authority → authority brings sponsors, merchants, and grant credibility → repeat.

---

## 4. What we build now — 30/60/90, ranked by leverage

The engine is done; almost everything below is **content and thin surfaces over existing code**. Estimates assume solo founder.

### Days 0–30 — ship what exists, open the reach layer
1. **Deploy and smoke-test live** (bot + web on the Hetzner stack; run `tools/eval_models.py` on real Uzbek; one credentialed OCR smoke per script). *The PM review's "do now" list — unchanged.* ~3–4 days.
2. **Launch the Telegram channel** (@avvalo — "scam of the week", 2 posts/week, comments on). Zero code. This is your forum v0 and your distribution spine. Ongoing: ~2–3 h/week, forever — see Hard Truths.
3. **Scam library v1 on avvalo.uz** — 11 pages, one per existing rule family, in RU + UZ-Latin first (Cyrillic next). Content drafted with AI, edited by you; each page ends in the checker. Code: a markdown loader + template + routes, ~1–2 days. Content: ~1 week part-time.
4. **Merchant interviews continue as the weekly gate** (target: 5/week toward the 20). Zero code.

### Days 30–60 — close the loop
5. **Story capture (opt-in)** — after positive feedback, offer "share your story"; pipe through the minimizer; store *only* the redacted text with explicit consent; forward to your operator chat for review (the unused `OPERATOR_ALERT_CHAT_ID` config is the ready-made hook). New table + one handler flow, ~2–3 days. Publish 1–2 curated stories/week to the channel + library pages.
6. **Scam Pulse #1** — extend the metrics CLI to aggregate `check_event.rule_ids` by month/language/face into a shareable one-pager. ~1 day of code, then a monthly ritual. Send it to journalists and to IT Park.
7. **Avvalo alpha per [FAMILY_VALIDATION.md](FAMILY_VALIDATION.md)** — 60–100 users, 21 days, with the PM review's cohort fixes (majority intended users, 30-day return, delayed-outcome question).

### Days 60–90 — decide with evidence
8. **IT Park submission** with the strengthened story: engine + two faces + two channels + a public content layer + real usage numbers + the Pulse. (The community layer materially improves the grant narrative: platform + social mission + data-for-good.)
9. **Merchant go/no-go:** three dated paid-pilot commitments → build billing (Payme/Click) and move Merchants front and center. Fewer → keep it a demo face and double down on Learn/Share growth.
10. **Forum decision:** only if the channel has real comment activity and stories flow weekly do we even discuss an owned forum. My default: the channel *is* the community until well past product-market fit.

❌ **Not building:** person/phone/card lookup (permanently), open forum (now), mobile app, more product faces (JobPass etc.), any new vertical before the merchant gate resolves. Future opportunities (voice checks, agentic verification, training, payment-context API, Group Guard, and the rest) are tiered with pull-forward criteria in [PRODUCT_HORIZONS.md](PRODUCT_HORIZONS.md) — that's where ideas wait without derailing this plan.

---

## 5. What attracts people (GTM for Uzbekistan, concretely)

1. **Telegram-first, always.** Telegram is the media layer of Uzbekistan; the channel, not the website, is the growth engine. The website's job is SEO and legitimacy.
2. **Stories are the shareable unit.** Nobody forwards "an AI analysis"; everyone forwards *"a woman in Tashkent almost sent 2M soum to a fake Payme support account — here's how the scam works."* Every story ends with the bot link.
3. **Shareable check results.** A "forward this warning" button on bot results (planned in the original design, still right) — warning a friend recruits them.
4. **SEO articles** for the searches people actually make in a panic ("предоплата мошенники телеграм", "soxta chek payme"). Compounding, free, and no one owns these queries in UZ today.
5. **Partnerships over ads:** scam-warning channel admins (cross-posts), universities/schools (digital-literacy talks with the bot as the takeaway), mahalla and parent groups. Later: a telco/bank sponsoring the channel — the Pulse is your pitch deck to them.
6. **The Pulse as PR.** A monthly, citable, data-backed "state of scams in Uzbekistan" makes you *the* reference. Journalists need this and nobody produces it.

---

## 6. The data story for investors — the version that survives a lawyer

Say this sentence in every pitch: **"We never store accusations about people; we aggregate how scams work."** Then show four assets:

1. **Trend intelligence (already accruing):** which scam families fire, in which language/region/face, week by week — the only real-time picture of consumer fraud patterns in Uzbekistan. Sellable in aggregate to banks/telcos as briefings; publishable as the Pulse.
2. **A labeled UZ/RU scam corpus (opt-in, de-identified):** stories + minimized examples. Uzbek is a low-resource language; a clean labeled fraud corpus in UZ-Latin/Cyrillic effectively does not exist anywhere. That's rare-asset territory for any future model work.
3. **The rule library:** locally-tuned detection patterns for CA scams, maintained against live data.
4. **Merchant workflow + outcomes** (post-pilot, consented): what merchants checked and what turned out fraudulent — the seed of the payment-provider integration story.

Honesty clause (also for yourself): **data is the supporting asset, not the headline.** Investors fund traction, retention, and revenue; the dataset makes those defensible. The pitch order is: users & habit → merchant revenue → *then* "and it compounds into a proprietary fraud-intelligence layer no clone can copy — collected legally."

---

## 7. Metrics — one number per surface

| Surface | North star | Supporting |
|---|---|---|
| Check | % users with a 2nd check ≤ 30 days | checks/week, confirmed "avoided payment", cost/check (≤ $0.03), safety-block rate |
| Learn | channel subscribers (weekly growth) | article → bot click-through, digest views, Pulse pickups/citations |
| Share | published stories/week | opt-in rate after checks, story → new-user attribution |
| Merchants | dated paid-pilot commitments (→ paying merchants) | interviews/week, trial→paid, churn |
| Platform | WAU across surfaces | % of new users from stories/articles (the flywheel working) |

---

## 8. Hard truths (read twice)

1. **The accusation database is dead and stays dead.** Every "can't we just let people look up a phone number?" idea re-opens criminal defamation exposure *for you personally* as the operator. The answer is permanently no in this jurisdiction. The legal data asset (§6) is the substitute — and it's genuinely good.
2. **Content is a grind, not a feature.** The Learn/Share layer only works at ~2 posts/week and 1–2 stories/week, in two languages, indefinitely. AI drafts + your edit makes it ~3 h/week. If you won't sustain that, don't start it — a dead channel is worse than none. This is the single biggest execution risk of this vision.
3. **The checker alone will not retain users** — episodic fear-driven usage was flagged in the very first design doc and it's still true. Learn/Share *is* the retention strategy, not decoration. But the reverse also holds: content without the checker is just another blog. The surfaces need each other.
4. **An open forum would be your worst month.** Empty rooms, spam, and users posting scammers' names and cards that you must moderate under defamation law. Curated stories give 80% of the value at 5% of the risk. Revisit forums only with real community traction and moderation help.
5. **"Help people" and "startup" only meet at the merchant gate.** The consumer side earns reach, mission, grant, and data — not revenue. If the 20 interviews don't produce three dated paid pilots, the honest conclusion is that Avvalo is a grant/sponsorship-funded public-good project for the next year, not a venture-scale startup yet. That's a legitimate outcome — but decide it with evidence, not vibes.
6. **Ship before you polish.** The repo is demo-ready and unreleased. Every week it sits unlaunched, you learn nothing. Steps 1–2 of §4 outrank everything else in this document.

---

## 9. Decisions I need from you

1. **Adopt "Check · Learn · Share" as the platform frame?** (This doc becomes the vision anchor; README/pitch language updates follow.)
2. **Commit to the content cadence** (2 channel posts + 1–2 stories per week, ~3 h/week) — or consciously drop the Learn/Share layer rather than half-run it?
3. **Story capture scope:** OK to add the opt-in story flow + redacted-story table (a consented, reviewed exception to "no content retention", per PRODUCT_GUIDE §3's opt-in derivative clause)? Needs a privacy-notice line and, before public alpha, a lawyer's read.
4. **Confirm the merchant gate stays hard:** 20 interviews / named price / 3 dated pilots before any billing code.

*My recommendations: yes, yes (with AI-assisted authoring), yes (lawyer-checked), yes.*
