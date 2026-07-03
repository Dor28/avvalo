# Avvalo — Product Guide (single source of truth)

> **Status:** Authoritative product direction (pre-build). Supersedes the accusation-graph model where they conflict.
> **Last updated:** 2026-06-21 *(rev. 2 — founder-review corrections applied to §1a, §2, §3, §7, §9, §10, §11, §12, §16)*
> **Owner:** Solo technical founder (Uzbekistan)
> **Read first.** This is the consolidated guide. The older docs remain as background and reusable detail — see §15 for what carries over and what is retired.

Legend: ✅ locked · 🔶 hypothesis / recommended default (validate, don't assume) · ❌ deliberate non-goal · ⚖️ open legal question (confirm with counsel)

---

## 1. Vision — "Check before you commit"

> **Avvalo helps ordinary people in Uzbekistan check a situation, message, document, payment, link, or deal — in Uzbek or Russian — before they commit money, identity, or trust.**

The one principle every product obeys, and the keystone of the whole direction:

> ✅ **Avvalo verifies the situation, document, or process — never the reputation of a person.**

We examine *what was sent to the user* and tell them the red flags, what to verify, and what to ask. We do **not** build, store, or publish a database of accusations about identifiable people.

Why this category is worth building now: Uzbekistan's e-commerce market was ~$1.2B in 2024 and is projected at $1.8–2.2B by 2027; Uzum alone reported $500M+ 2025 e-commerce GMV and $1.2B across fintech. As commerce digitizes, the need to "check before you commit" scales with it. *(Sources in [ADJACENT_PRODUCT_IDEAS.md](ADJACENT_PRODUCT_IDEAS.md) §1.)*

---

## 1a. What's locked vs. what's a hypothesis

*(Added after founder review, 2026-06-21. The guide is the authoritative direction, but several pieces are explicitly experiments — do not build as if they're proven.)*

**🔒 Locked — build on these:**
- The **vision** (§1) and **safety principles** (§4).
- The **shared engine** (§3).
- The **Avvalo micro-MVP** (§7) — one entry behaviour.
- **Avvalo Merchants as the revenue hypothesis** (§8) — start merchant interviews now.
- **No accusation database** (§14).

**🔬 Open — hypotheses to validate, NOT settled:**
- **Telco/bank sponsorship** as a payer (§7, §11) — unproven; enterprise sales is slow.
- **The product sequence after Avvalo** (§10) — let merchant demand, not this plan, decide the order.
- **The Deal Check vertical** (§9) — choose vehicles *or* electronics only once a usable data source exists.
- **"Pattern database = moat"** (§3) — it's a useful asset, not a moat.
- **Database-registration & foreign-processing conclusions** (§12) — confirm with counsel / the regulator.

---

## 2. Why we pivoted from the accusation-graph model

The original brief ([fraud_intelligence_startup_prompt.md](../prompts/fraud_intelligence_startup_prompt.md)) and [PRODUCT_DESIGN.md](PRODUCT_DESIGN.md) described a *fraud-intelligence graph*: silently store entities (phones, handles, cards) and surface *"this person was reported N×."* A 2026-06-21 legal + monetization review concluded that model concentrates risk in one layer — the stored, queryable database of accusations about identifiable people:

1. **Criminal defamation.** In Uzbekistan defamation is a crime (Criminal Code **Art. 139** slander, **Art. 140** insult; online dissemination is an aggravating form), and "reported for fraud" imputes a crime (**Art. 168**). Civil liability (Civil Code ~Art. 100) puts the burden of proving a statement *true* on the operator.
2. **A weak, contestable lawful basis** for processing the *non-consenting accused's* personal data. *(Note — wording corrected: the Personal Data Law (ZRU-547) has both consent **and** non-consent grounds, so processing was never **categorically** illegal. But for a commercial database that accuses identifiable people, the basis is shaky and contestable — risk enough.)*

**The pivot is a risk-reducing product decision, not a claim that the old model was strictly unlawful.** By verifying the *situation* (the user's own forwarded content) instead of rating *people*, both risks shrink dramatically, and the product gets simpler, safer, and easier to monetize honestly. We keep the useful engine; we drop the accusation database. *(Residual compliance in §12.)*

---

## 3. The shared engine ✅

All products are thin packages over **one backend**. Build the engine once; package it for each audience.

```
            ┌──────────────────────────────────────────────┐
 Telegram ─▶│  intake (guided categories + text + images)  │
            │   → OCR (LOCAL / on-prem, v1) UZ + RU         │◀─ Web
            │   → PII minimization → minimized text only    │
            │   → hybrid analysis: rule checklist + LLM     │
            │   → 🚩/✅/❓ output (no verdict, no naming)     │
            │   → no retention by default (v1)               │
            └──────────────────────────────────────────────┘
```

- **Intake:** guided categories + freeform text + image upload (screenshots, photos).
- **OCR — local-first ✅:** run **OCR locally / on-prem for v1**. A cloud OCR sees the *raw* screenshot (full cards, faces, third parties) *before* any redaction is possible — a cross-border-transfer problem SCCs don't fully solve (§12). Do OCR on home soil; send only minimized text onward.
- **Minimization:** strip/minimize PII and **never store full card numbers**; strip EXIF/GPS from images; send only **genuinely minimized text** to the LLM.
- **Hybrid analysis (the locally-tuned asset):** a deterministic, versioned, per-category **rule checklist** with UZ/RU keyword sets runs first and is authoritative; the **LLM** adds nuance and writes the UZ/RU output. The LLM never emits a score or a "safe/scammer" verdict. *(Engine detail: [PRODUCT_DESIGN.md](PRODUCT_DESIGN.md) §8a.)*
- **Pattern capture (later; useful asset — 🔬 not the moat):** the Avvalo micro-MVP retains **no submitted content or pattern examples by default**. After validation, Avvalo may retain only an **explicitly opt-in, manually reviewed, genuinely de-identified derivative** that improves the rules and powers community pattern-alerts (*"a new fake-delivery scam is circulating"*). The submitter's consent alone does **not** cover every person appearing in a forwarded message or screenshot. Useful — but **competitors can reproduce rules, anonymized examples, and alerts**, so don't mistake it for defensibility. The **stronger future moats** are: local **payment-provider integrations**, **merchant workflows + historical outcomes**, **labeled receipt/document examples**, **distribution partnerships**, and a **trusted UZ/RU safety brand**.
  - **De-identification caveat:** removing obvious identifiers (names/phones/cards/usernames/faces) does **not** guarantee de-identification — distinctive wording and transaction context can still re-identify a person. Do not retain the derivative unless manual review confirms that re-identification risk is acceptably low; treat every retained example as still-sensitive.

---

## 4. Output & safety principles ✅

Every product returns the same fixed block, and never a verdict:

- 🚩 **Red flags** found in what the user sent.
- ✅ **What to verify** — concrete actions to confirm legitimacy.
- ❓ **Questions to ask** the counterparty before committing.

Hard rules:
1. Verify the **situation/document/process — not a person**.
2. Never say **"safe," "scammer," or "fraud confirmed."**
3. Give **concrete verification actions**, not a fear score.
4. Store **only** what creates lawful, consented, reusable value.
5. **Minimize** every community example (no names/phones/cards/usernames/faces — and remember §3's caveat that this alone isn't full de-identification).
6. Keep the **free product genuinely useful**.
7. Let **organizations pay** to support, distribute, or embed protection — never let a sponsor influence a result, and never sell personal data.
8. **Build one narrow wedge before** combining ideas into a universal assistant.

---

## 5. Languages ✅

Uzbek (**Latin and Cyrillic**) + Russian, from v1. Auto-detect input language; reply in the same. OCR, rule keyword sets, and output all cover all three.

---

## 6. The product portfolio

Three products, one engine. The order below is the **current working hypothesis — not locked** (see §1a, §10).

| # | Product | Audience | Role | Who pays | Legal risk |
|---|---|---|---|---|---|
| **1** | **Avvalo** | Families / consumers | Free community wedge — reach, mission, brand | Family plan + sponsor *(both hypotheses)* | 🟢 Low |
| **2** | **Avvalo Merchants** (avvalo.uz/merchants) | Small TG/IG merchants | The revenue engine — recurring B2B | Merchant subscription | 🟡 Low–med |
| **3** | **Deal Check** | Big-ticket buyers | Parked until a vertical + data source exist | Per-report + referral fees | 🟡 Low–med |

Parked for later (don't build now): **JobPass, Fine Print, Complaint, LinkSafe** — see §17.

---

## 7. Phase 1 — Avvalo (free / community)

**Concept.** A Telegram-first safety assistant for protecting parents, relatives, and less digitally confident family members.

**✅ The v1 is ONE behaviour, not six features.** The whole product the user sees is a single habit:

> *"Forward any suspicious message or screenshot before you respond or pay."*

The user does one thing; Avvalo replies with the 🚩/✅/❓ read in UZ/RU. **Internally** the engine recognizes several patterns — fake bank-support, "your child is in trouble" / emergency, payment requests, suspicious links & QR codes, job/investment offers — but these are **detection categories behind one entry point, never presented to the user as separate products.**

**Output:** the 🚩/✅/❓ block + the manipulation pattern explained + concrete verification steps. Never "safe"/"scammer."

**Free tier:** limited checks · UZ/RU explanations · community scam-pattern alerts · short education guides.

**Paid family plan (later, 🔬 a hypothesis):** up to 5 family members · higher/unlimited checks · shared family alerts (with explicit consent) · priority analysis · monthly "new scams affecting families" digest.

**Who pays — 🔬 primary monetization hypothesis to validate, NOT an assumption:** the family subscription is one option; the bigger bet is a **telecom/bank bundle or sponsored digital-safety campaign** (B2B2C). Enterprise sponsorship can take **months** and may require procurement, security review, and significant traction. **Do not build Avvalo assuming a sponsor will appear.** Keep costs near zero, and validate willingness-to-pay (family plan) and merchant revenue (Avvalo Merchants) **in parallel.**

**Proves:** whether the one-behaviour wedge earns reach and repeat use, cheaply — and seeds the scam-pattern content.

---

## 8. Phase 2 — Avvalo Merchants (paid / merchant, avvalo.uz/merchants) ✅ *(the revenue hypothesis)*

**Concept.** A Telegram assistant for small merchants selling via Instagram, Telegram, and informal channels — the **revenue bet**.

**What merchants forward:** a payment screenshot · an order conversation · a delivery request · a return/refund request · a suspicious customer message.

**What Avvalo checks:** whether receipt fields are internally consistent · whether screenshot editing is suspected · whether order vs. claimed-payment amounts match · whether the chat matches known fake-courier/refund patterns · **what the merchant must verify in their real bank/payment app.**

> ✅ **Hard rule:** never claim money *arrived* from a screenshot. A definitive payment result requires an **authorized payment-provider integration** — which is the moat, added later.

**The moat.** Image-forensics is adversarial and only a *hint*. The must-have product is the **verification checklist + authorized payment-provider API confirmation** ("did the money really land in your account?"). Sell that; treat forensics as a supporting signal.

**Monetization:** monthly merchant subscription · team accounts for small shops · payment-provider/marketplace integration (later) · white-label merchant-safety assistant.

**Why it's the revenue bet:** the only idea with all four of **payer + frequency + ROI + retention** — merchants face suspicious orders repeatedly (recurring need, not a one-time fear product), and one caught fake-payment pays for a year.

> **🔬 Validate now, in parallel with Avvalo:** interview merchants and test willingness-to-pay from week 1. **If merchants offer to pay before consumers develop repeat usage, move Avvalo Merchants forward immediately** — the §10 order is not locked.

**Note:** merchants are a **different audience and go-to-market** from Avvalo's families — the engine is shared, the GTM is not.

---

## 9. Phase 3 — Avvalo Deal Check (paid reports) 🔶 *(parked)*

**Concept.** A pre-purchase assistant for expensive transactions — cars, electronics, apartments, rentals.

**What the user uploads:** the listing · seller conversation · payment request · available documents.

**What Avvalo provides:** a deal-specific verification checklist · missing-document detection · price & payment red flags · questions for the seller · inspection/notary/payment-safety steps · a structured "what is known / what is missing" report.

**Monetization:** one-time paid deal reports · premium vehicle/real-estate reports · **referrals** to inspection, insurance, legal, and notary services (the real upside on big-ticket deals).

**🔬 Stays parked until:** **one vertical is chosen (likely vehicles or electronics) AND a useful/licensed data source is available.** Without real data integrations it's only a generic checklist generator — so don't schedule it as "the third product"; unpark it when a vertical + data source are in hand.

---

## 10. Build order & sequencing 🔶 (working hypothesis — not locked)

**Current hypothesis: Avvalo → Avvalo Merchants → Deal Check — but the order after Avvalo is decided by evidence, not by this plan.**

- **Avvalo is a 2–4 week experiment**, not a multi-month build — ship the one-behaviour micro-MVP (§7), then measure the success/failure gates (§16).
- **Interview merchants in parallel from week 1.** **If merchants offer to pay before consumers develop repeat usage, move Avvalo Merchants forward immediately.**
- **Deal Check stays parked** until a vertical (vehicles or electronics) is selected and a useful data source is available (§9).

| Phase | Ships | Proves |
|---|---|---|
| **1 — Avvalo** *(2–4 wk experiment)* | Shared engine + one-behaviour checker + first community alert | Cheap reach + repeat use? |
| **2 — Avvalo Merchants** *(unlock on merchant demand)* | Merchant analysis + verification checklist + subscription (+ payment integration later) | Recurring revenue + retention |
| **3 — Deal Check** *(unlock on vertical + data)* | Deal report (checklist first; data integrations later) + referrals | High-value transactional revenue |

> **Honest watch-item:** Avvalo-first defers revenue, and its payer is an unproven sponsorship hypothesis (§7). So keep running costs near zero, run **merchant validation alongside** from day one, and be ready to flip to Avvalo Merchants the moment the evidence says so.

**Parallel, non-engineering (start in Phase 1):** merchant interviews · telco/bank sponsorship discovery · scam-pattern content authoring (rules + education, UZ-Latin/Cyrillic + RU) · the legal confirmations in §12.

---

## 11. Monetization & sustainability 🔶

Free for the core action; the money comes from elsewhere. Consumers are the **audience**, not the main **payer**. Each line below is a hypothesis to validate, not booked revenue.

- **Merchant subscriptions** (Avvalo Merchants) — the **primary** revenue bet; validate willingness-to-pay now.
- **Telco/bank bundles & sponsored campaigns** (Avvalo) — *a hypothesis; unproven and slow (§7). Don't depend on it.*
- **Paid deal reports + referral fees** (Deal Check) — after unparking.
- **White-label** checkers for consumer organizations, employers, schools.
- **Optional tips / Telegram Stars** — cost-offset only, never the model.

Non-negotiable: **never sell personal data, and never let a sponsor influence an analysis result.**

---

## 12. Legal & privacy posture ⚖️ (open — confirm with counsel, do NOT lock)

The §1 principle (verify the situation, not the person) **materially reduces** the *big* risks (criminal defamation + processing the non-consenting accused), but does not eliminate them: forwarded content can still contain identifiable, non-consenting third parties. What remains is ordinary data-protection compliance — real, because we still process personal data, but the **obligations below are open questions to confirm with a licensed Uzbek lawyer / the regulator, not locked product statements.**

**Settled enough to act on now:**
- **Form an entity (MChJ/LLC)** as the operator / publisher of record.
- **First-run consent + clear privacy notice** (what's stored, why, retention, how to delete); record consent version + timestamp.
- **Data minimization** — never store full card numbers; strip EXIF/GPS; keep only minimized examples; **local OCR for v1** (§3).
- **Disclaimers** — an explanation tool, **not** legal or financial advice; never "safe"/"scammer."
- **Honor data-subject access / correction / deletion** requests.

**⚖️ Open — confirm with counsel / regulator (these are NOT locked):**
- **Which authority + whether/when registration is required.** Per the **official registry pd.gov.uz**, the responsible body is the **Migration & Personalization Department under the Ministry of Internal Affairs (MVD)**; several secondary/law-firm sources still name a *Personalization Agency under the Ministry of Justice* — **confirm the current authority.** Registration is **not** unconditionally "before any processing": the amended **Art. 20** ties mandatory registration to databases that must be stored domestically under **Art. 27¹**, while **Art. 31** retains broader registration language — a genuine tension. Confirm *whether, when, and which* databases must be registered.
- **Foreign processing is only PARTLY solved by SCCs.** The 27 Mar 2026 amendment ([lex.uz/docs/8099215](https://lex.uz/docs/8099215)) does permit some data abroad via adequacy / SCCs / a listed standard (biometric + telecom-subscriber data stay domestic). **But** Art. 15 still governs cross-border *transfer*, Art. 31 separately governs *entrusting processing* to a third party, the submitting user's consent does **not** cover every person shown in a screenshot, and **cloud OCR sees the raw screenshot before any redaction is possible.** SCCs cover only part of the problem.
  - **→ v1 product decision (de-risks all of the above):** **run OCR locally / on-prem**, then send only **genuinely minimized text** to the LLM (already baked into §3). Revisit cloud OCR only after counsel signs off.

> Not legal advice. Engage a licensed Uzbek *advokat* to confirm the registration trigger and the foreign-processing path, and to draft the ToS + privacy policy (UZ Latin/Cyrillic + RU) before launch. *(See the current consolidated Personal Data Law + the 2026 amendment.)*

---

## 13. Metrics

- **Avvalo:** weekly active users, checks/user, **repeat use** (2nd check in 14 days), share/invite rate, "confirmed avoided a payment," cost per check.
- **Avvalo Merchants:** merchant-interview → willingness-to-pay signal, trial→paid conversion, monthly churn, revenue/ARPU, checks/merchant/week.
- **Deal Check:** (after unparking) reports sold, referral revenue, repeat rate.
- **Cross-cutting:** cost per check trending **down**; rule-coverage & education freshness.

---

## 14. Non-goals ❌

- ❌ A stored/queryable **database of accusations about identifiable people**.
- ❌ A **"this person is a scammer" lookup**, scammer clusters, or "reported N×" output about a person.
- ❌ **Risk scores** or **"safe" verdicts**.
- ❌ Selling personal data; letting sponsors influence results.
- ❌ Public/shareable accusation pages.
- ❌ Building all the products at once, or presenting Avvalo as six features (build one wedge / one behaviour first).

---

## 15. Relationship to the other docs (supersession map)

| Doc | Status |
|---|---|
| **This guide** | ✅ Authoritative product direction. Start here. |
| [PRODUCT_DESIGN.md](PRODUCT_DESIGN.md) | Background. **Reuse:** intake §6, output §5, languages §7, hybrid engine §8a, OCR/redaction/privacy §11a, usage limits §10, education. **Retired:** silent accusation graph & clusters §8b/§8e, report-state machine §8c, "reported N×" evidence line, standalone scammer reports, the accused-dispute machinery §8f/US-6.1, B2B fraud-intel-API-as-the-business, "graph-match rate" as the headline metric. |
| [ADJACENT_PRODUCT_IDEAS.md](ADJACENT_PRODUCT_IDEAS.md) | Source of the reframe and the 8 product ideas. This guide selects and sequences three of them. |
| [FUNDABILITY_AND_GTM.md](FUNDABILITY_AND_GTM.md) | Background. The "anti-fraud data infrastructure / B2B-API" thesis is **deprioritized** in favor of merchant subscriptions + sponsorship; the IT Park / regional / de-risk-the-founder advice still applies. |
| [USER_STORIES.md](USER_STORIES.md) | Background. Epic 1 (check), Epic 4 (education), and the cross-cutting consent/limits/redaction stories carry over; Epics 2/3/5/6 (reports, accusation-based alerts, accusation moderation, the accused) are retired with the graph. |
| [SESSION_DECISIONS.md](SESSION_DECISIONS.md) | History — includes the 2026-06-21 pivot entry. |

**Carried-over engine = reusable code/spec.** The pivot changes *what we store and output about people*, not the OCR → minimize → rules + LLM → 🚩/✅/❓ pipeline.

---

## 16. Open decisions / next deliverable

1. **Tech stack** — Telegram framework; **OCR — local/on-prem for v1** (§12), UZ Latin/Cyrillic + RU; LLM provider (fed only minimized text); a **relational DB is enough** (no graph DB — there's no accusation graph); web framework; UZ-or-compliant hosting.
2. **Pricing** — Avvalo Merchants monthly tier; size it **bottoms-up** (active UZ TG/IG merchants × realistic paying % × price), not from the $2B TAM.
3. **Legal confirmations** (§12) — the registration trigger and foreign-processing path, with a local lawyer.

> **Completed 2026-06-21:** [FAMILY_VALIDATION.md](FAMILY_VALIDATION.md) is the Avvalo *validation* spec—not a full technical build spec. It defines:
> 1. **one entry flow** (the single "forward a suspicious message" path),
> 2. **five example outputs** (five real pasted scenarios → the exact 🚩/✅/❓ reply),
> 3. **retention rules** (what's kept, minimized, or discarded, and for how long),
> 4. a **cost ceiling per check**, and
> 5. **measurable success / failure gates** (what result greenlights building further vs. kills or pivots it).
>
> **Next:** implement the validation build and run its private alpha. The full engine schema comes *after* this experiment validates demand.

---

## 17. Idea backlog (parked, not now)

Kept for later; each reuses the same engine:

- **JobPass** — job/visa/migration-scam checks. High community impact (large UZ labor-migration market); monetization is lumpy/partner-funded (migration orgs, recruiters, sponsored worker-safety). The mission-first alternative to Deal Check.
- **Fine Print** — plain-language contract explainer (loans, rentals, services). Broad/horizontal; pay-per-doc + white-label. Must stay an explanation tool, not a lawyer substitute.
- **Complaint** — consumer-rights assistant that drafts a structured complaint in UZ/RU. A feature or grant-funded module more than a standalone business.
- **LinkSafe** — link/QR/phishing checker. Globally commoditized — keep it as a **free feature inside Avvalo**, not a standalone product.
- **Antispam / Group Guard** — automatic anti-scam protection for Telegram **groups & channels**: add the live bot ([@Avvalo_official_bot](https://t.me/Avvalo_official_bot)) as an admin and it screens incoming messages with the shared engine, removing scam links / phishing / spam and CAPTCHA-gating new joiners. Reuses the engine but flips from *user-initiated checks* to *passive monitoring + automated content moderation* — so it needs a conservative default, an admin appeal path, and its own install-time privacy notice (it reads group messages, not private forwards). Detail in [ADJACENT_PRODUCT_IDEAS.md](ADJACENT_PRODUCT_IDEAS.md) §13. 🔬 future.
