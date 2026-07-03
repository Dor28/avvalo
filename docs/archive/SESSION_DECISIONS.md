# Avvalo — Session Decision Log (2026-06-17)

> A chronological record of the founding PM session — the decisions and *why*. This is the "how we got here" companion to [PRODUCT_DESIGN.md](PRODUCT_DESIGN.md) (the "what we decided").

## Origin
- Brief: [fraud_intelligence_startup_prompt.md](../prompts/fraud_intelligence_startup_prompt.md) — a fraud-intelligence graph for Central Asia.
- Founder: solo, technical, based in Uzbekistan.

---

## Decisions, in the order they were made

### 1 — Direction
- **Wedge:** broad AI "fraud read" front door — founder chose breadth over narrow history-lookup ("scams are varied"). *(Refined in step 9.)*
- **Target user:** regular one-off consumers checking before paying / sharing data.
- **Cold start:** lean on AI for day-1 value. *(Revised in step 9.)*
- **Languages:** Uzbek + Russian, both.

### 2 — Core UX
- **Output:** 🚩 red flags + ✅ verify + ❓ ask. **No score, no verdict** (liability).
- **Intake:** guided categories + freeform text/images.
- **Data layer:** silent entity capture from day 1 (the moat).

### 3 — Limits & money
- **Usage limits:** separate cheap lookups (unlimited) from costly AI (limited); **soft-degrade, never hard-block**; cache identical inputs; ~10/day Telegram, ~3–5/day web. *(Superseded the founder's initial flat 3/day.)*
- **Monetization:** no payment in v1; donations later as a **cost-offset only**, explicitly not the business model. B2B API is the real future revenue.

### 4 — Analysis engine
- **Hybrid:** deterministic per-category rule checklist (authoritative, unit-testable, UZ+RU) **+** LLM (nuance, UZ/RU phrasing, the verify/ask parts). The LLM never overrides rules and never emits a score.

### 5 — Fundability review (VC-advisor pass)
- Reframe to **"anti-fraud data infrastructure"**; land B2B LOIs; IT Park; regulation-as-credibility; de-risk the solo founder; regional story. → captured in [FUNDABILITY_AND_GTM.md](FUNDABILITY_AND_GTM.md).

### 6 — Architecture & web
- **API-first:** one backend, multiple thin UIs (Telegram + web). The **check is identical on both**; no analysis logic lives in a client.
- Web kept simple at first (UX shell, not a weaker check).

### 7 — Function list (8 functional decisions, all recommended path)
- Standalone "report a scam" flow · threshold + admin-review moderation · instant quick-lookup · store image hashes now / defer matching · share + invite · watch + notify alerts · `/history` · contextual education tips.
- Identity nuance: alerts/history/report-attribution are **Telegram-first** (web anonymous in v1).

### 8 — Entity priorities
- Graph spine = **persistent identity** (Telegram / Instagram / phone) + a **scammer-cluster** node + **scam-pattern tags**. Cards demoted to a supporting signal (**BIN + last4 + hash only**). Also lowers data-law/liability surface.

### 9 — External LLM critique review
Founder shared a critique from another model. Verdicts below. The three contested points (which touched earlier decisions) were resolved by the founder:
- **Wedge:** hero wedge (seller / prepayment fraud) **+ keep broad intake**.
- **Cold start:** **seed before launch** (curate public reports + Telegram partnerships + manual founder review + private alpha; label seed data `imported`).
- **Web:** **text check + lookup** in v1; anonymous image upload + reporting **gated/deferred**.

---

## Critique scorecard

| # | Critique point | Verdict | Action taken |
|---|---|---|---|
| 1 | Wedge too broad | Your call — right about focus | Hero wedge §3a, broad intake kept |
| 2 | Risks becoming an AI wrapper | Partly (already mitigated) | Story-only demoted to fallback; entity-extraction-rate metric |
| 3 | Cold start not solved | Agree (real gap) | Seeding §3b added to v1 |
| 4 | "N reports" underdefined | Agree fully | Report-state machine + independence rules §8c |
| 5 | Telegram signals unavailable | Agree (technically correct) | Rule library fixed §8a + API-reality note |
| 6 | Web increases abuse before moat | Your call | Web scope narrowed §8 + matrix |
| 7 | Legal/privacy needs a spec | Agree (biggest gap) | Privacy spec §11a (launch blocker) |
| 8 | Monetization postponed | Agree | B2B-buyer interviews §11 |
| 9 | Success metric weak | Agree | Metrics expanded §13 |

---

## Still-open items
- Confirm usage-limit numbers (§10).
- Confirm primary success metric (§13).
- **Tech stack** (Telegram framework, OCR for RU+UZ, LLM provider, DB, web, hosting).
- **Next deliverable: the data schema** (identity-cluster, report-state machine, `imported` label, privacy/retention fields).

---

## 2026-06-20 — Pre-build plan review (scope confirmed, specs added)

A second PM pass, immediately before implementation.

- **Scope decision:** advised to cut v1 to a thin Telegram + text graph-loop slice; **founder kept the full §16 v1** and chose to improve the plan *in place*. Discipline therefore shifts from *what* to *what-order* → new **§17 build order** (M1 core loop → M2 trust → M3 growth → M4 web → M5 admin; seeding / B2B / legal / content run in parallel from M1).
- **17 improvements folded into the spec** before the schema:
  - **New sections:** §8d entity extraction & normalization · §8e cluster merge/unmerge governance · §8f dispute & removal flow · §17 build order · §18 content & ops workstreams.
  - **Updated:** §5 (empty-state template + evidence-line-as-hero) · §7 (UZ Latin **and** Cyrillic) · §8c (check ≠ report in counts, "reported N×" = corroborated/verified over a 30-day window, reporter trust-weight, two-sided abuse) · §9 (first-run consent) · §10 (cache the LLM output, never the graph; quick-lookup rate-limit/oracle) · §11a (OCR is cross-border too; image lifecycle / EXIF / faces) · §14 (relational DB is enough — no graph DB; reconcile the two data-model sources).
  - **User stories added:** US-2.4 (two-sided abuse), US-6.1 (dispute & removal — new persona *Sardor, the accused*), US-X.4 (consent), US-X.5 (no lookup leakage).
- **Next deliverable unchanged:** the data schema — now explicitly the **union** of the original brief's tables ([intial.md](../prompts/intial.md)) and the §8b–§8f model.

---

## 2026-06-21 — Pivot: "verify the situation, not the person"

A legal-risk + monetization review (Claude acting as Uzbek counsel + strategist). The project pivots from the fraud-intelligence **accusation graph** to a **"check before you commit"** assistant that verifies the situation / document / process — never a person's reputation. New authoritative doc: [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md).

- **Driver:** the stored database of accusations about identifiable people concentrated two existential risks — **criminal defamation** (Criminal Code Art. 139 slander / 140 insult; "reported for fraud" imputes Art. 168; civil burden of proving truth falls on the operator) and **no lawful basis** to process the non-consenting accused's data (Law on Personal Data, ZRU-547). The fix is the design principle, not more governance.
- **Localization update:** Uzbekistan **relaxed data-localization on 27 Mar 2026** (lex.uz/docs/8099215) — a foreign LLM/OCR is now compliant via adequacy / SCCs / listed standard (biometric + telecom-subscriber data stay domestic). Supersedes [PRODUCT_DESIGN.md](PRODUCT_DESIGN.md) §11a "local storage is a launch blocker."
- **Portfolio (one engine, three packages), chosen sequence:** **Avvalo** (free/community) → **Avvalo Merchants** (paid/merchant) → **Deal Check** (paid reports). JobPass / Fine Print / Complaint / LinkSafe parked (PRODUCT_GUIDE §17).
- **Monetization:** merchant subscriptions + telco/bank sponsorship + paid reports/referrals + white-label; never sell data or let a sponsor influence a result. The B2B fraud-intel-API thesis is **deprioritized**.
- **Retired with the graph:** silent accusation graph & clusters, report-state machine, "reported N×" output about a person, standalone scammer reports, the accused-dispute machinery, graph-match-rate as the headline metric.
- **Next deliverable:** an Avvalo **validation spec** (one entry flow, five example outputs, retention rules, cost ceiling, success/failure gates) — *not* a full build spec.
- **Rev. 2 (same day, after founder review):** corrected the guide — Avvalo narrowed to **one behaviour** (not six features); **sequence unlocked** (let merchant willingness-to-pay decide the order after Avvalo); **sponsorship reframed** as an unproven hypothesis; **pattern-DB demoted** from "moat" (reproducible — real moats are payment integrations / merchant outcomes / labeled data / distribution / brand); legal section corrected (contested authority — official **pd.gov.uz** says **Migration & Personalization Dept under the MVD**, not MoJ; registration **not** categorical — Art. 20/27¹ vs Art. 31 tension; SCCs only **partly** solve cross-border per Art. 15/31 + cloud-OCR-sees-raw-image → **local OCR for v1**); "no lawful basis" softened to "weak/contestable basis." See the guide's new §1a.

---

## Artifacts produced this session
- [PRODUCT_DESIGN.md](PRODUCT_DESIGN.md) — the earlier MVP spec (now background / engine reference).
- [USER_STORIES.md](USER_STORIES.md) — 17 user stories across 6 epics.
- [FUNDABILITY_AND_GTM.md](FUNDABILITY_AND_GTM.md) — fundraising & GTM strategy.
- [ADJACENT_PRODUCT_IDEAS.md](ADJACENT_PRODUCT_IDEAS.md) — the reframe + 8 product ideas *(2026-06-21)*.
- [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) — the consolidated, authoritative product guide *(2026-06-21)*.
- This log.
