# Avvalo — Product Design Document

> **ARCHIVED — DO NOT USE FOR PRODUCT SCOPE OR PRIORITY.** It contains the retired accusation-graph
> era. Current direction: [PRODUCT_GUIDE.md](../PRODUCT_GUIDE.md).

> **Status:** MVP definition (pre-build). Living document.
> **Last updated:** 2026-06-20
> **Owner:** Solo technical founder (Uzbekistan)

Legend: ✅ = locked decision · 🔶 = recommended default, not yet confirmed · ❌ = explicit non-goal

---

## 1. One-line definition

> **An AI fraud-check assistant for Uzbekistan.** Paste any suspicious situation — a payment request, a seller, a job offer, an investment pitch — in Uzbek or Russian, and get back the specific red flags, what to verify, and exactly what to ask *before* you send money or share data. Every check quietly builds a local fraud-intelligence graph.

Available as a **Telegram bot** and a **web checker**, both running on one shared backend.

---

## 2. Problem

People buying, selling, and transacting through Telegram, classifieds, Instagram, marketplaces, and informal channels in Central Asia face constant fraud risk: fake sellers, reused photos, stolen listings, fake payment screenshots, suspicious cards/phones, duplicated identities, too-good prices, and sellers vanishing after prepayment.

Two things make a naive "risk score" product fail:
1. **B2C fear products monetize badly** — users check once during a scare, then forget.
2. **Safety verdicts are dangerous** — saying "looks safe" and being wrong destroys trust and creates liability.

So the product must lead with **evidence and education**, not a verdict, and must build a **defensible local data asset** underneath.

---

## 3. Strategy — the two-layer design ✅

| Layer | What it is | Why |
|---|---|---|
| **Visible layer (the wedge)** | Instant AI "fraud read" on whatever the user pastes | Day-1 value with an empty database; viral; easy to explain |
| **Silent layer (the moat)** | Every check extracts + stores entities into a graph | Defensibility that compounds; what no AI-only clone can copy |

**The AI is the spoon; the graph is the meal.** Users get an instant read today; we accumulate proprietary fraud data for free. In ~6 months the graph lets us say *"this card was reported 3× this month"* — the high-value, evidence-based output AI alone can never produce. That is when the moat and B2B monetization become real.

This **deliberately diverges** from a "data-graph-first" plan: we lead with AI UX for reach, and grow the graph behind it.

---

## 3a. Hero wedge ✅

*(Added 2026-06-17, after external review.)*

**Hero wedge.** Intake stays broad (all categories — the virality/UX win), but v1 *learning, seeding, and rule-tuning* concentrate on one painful, repeated behavior: **seller / prepayment fraud in Telegram/Instagram commerce** (buyer pays a deposit or full amount up front; seller vanishes). This niche yields the richest *repeated* identity entities (handle + phone + photo, sometimes card). Other categories are supported but not optimized in v1.

**Anti-wrapper focus.** Checks that extract **≥1 entity** are the priority — they feed the graph. *Story-only* analyses (no extractable entity, US-1.3) are a **fallback**, not the core. We track **entity-extraction rate** (Section 13) to guard against drifting into a pure AI wrapper.

---

## 3b. Graph seeding ✅

*(Added 2026-06-17.)* **The graph must not launch empty** — AI alone returns a one-time *"no known records,"* useful once, not habit-forming. So we seed the hero niche before/at launch, from:
- **Curated public scam reports & warning lists** (import).
- **Telegram community partnerships** — scam-warning channel/group admins sharing report history.
- **Manual founder review** — hand-curated known scammers.
- **Private alpha reports** from one narrow commerce niche.

**Seeded data is marked separately from verified user reports** — stored in the `imported` state (Section 8c) and shown only as *"imported / unverified,"* never as a verified user report. It informs; it never certifies.

---

## 4. Target user (v1) ✅

**Regular consumers** about to pay someone or share data, who want a quick gut-check first. (We accept that retention and direct monetization are weak for this segment — it's chosen for reach and data volume, not revenue.)

High-frequency buyers/resellers and B2B customers are the *future* business, not the v1 design target.

---

## 5. Output design ✅

Every analysis returns a **fixed three-part block** — never a score, never a "safe/unsafe" verdict:

- 🚩 **Red flags found** — specific warning signs detected in what they sent.
- ✅ **What to verify** — concrete actions to confirm legitimacy.
- ❓ **Questions to ask** — what to ask the seller/counterparty before paying.

Plus, when an extracted entity matches the graph: **⚠️ evidence line** (e.g., *"this card was reported 2× this month"*).

**Rationale:** safest (no liability), most useful, most shareable. A number trains users to stop thinking and exposes us when wrong.

**The evidence line is the hero.** When the graph returns a hit, the ⚠️ evidence line is the single most decisive, screenshot-worthy element — it carries the weight a verdict normally would, *without being one.* Render it **first and visually dominant** when it fires; the 🚩/✅/❓ block follows. The graph evidence — not the AI prose — is what makes a result worth forwarding (the virality loop, §13).

**Empty-state output (the launch-day default).** At launch the graph is near-empty, so *most* checks return no match. This is a first-class output, not an afterthought:

> *"ℹ️ No known records for this seller / number yet. **This does not mean it's safe** — it means no one has reported it to us. Here's what to check before you pay:"* → then the full 🚩/✅/❓ block.

Never let "no records" read as a clean bill of health (the core liability trap). The 🚩/✅/❓ block always runs, so the user gets value even with an empty graph.

---

## 6. Intake design ✅

**Guided categories + freeform.** The bot/web asks *"What are you checking?"* with buttons:
`Payment` · `Seller` · `Job offer` · `Investment` · `Other`
→ then accepts **freeform text and image uploads** (screenshots, photos).

Rationale: pure "paste anything" degrades AI accuracy; strict fixed fields ignore that scams are messy. Guided categories keep the AI focused while still handling anything.

---

## 7. Languages ✅

**Uzbek + Russian**, both, from v1. Auto-detect input language; reply in the same. (OCR + entity extraction must handle both.)

**Uzbek is written in two scripts — Latin *and* Cyrillic.** Language detection, the rule-layer keyword sets (§8a), and OCR must all handle **UZ-Latin** and **UZ-Cyrillic** in addition to Russian. Budget for ~3 keyword sets, not 2.

---

## 8. Architecture decision (product-level) ✅

**API-first: one backend, multiple thin UIs.** The product *is* the backend. UIs are interchangeable faces.

```
                ┌─────────────────────────────────────────────┐
                │                CORE BACKEND                  │
   Telegram ───▶│  intake → OCR → entity extraction +          │
   bot          │  normalization → graph store/lookup →        │◀─── Web
                │  AI orchestration → 🚩/✅/❓ output →          │     checker
                │  report capture → abuse/rate-limit            │
                └─────────────────────────────────────────────┘
```

- **Client 1 — Telegram bot:** full guided flow. The viral wedge. Brings free identity + anti-spam.
- **Client 2 — Web checker:** the **same check, on the web** — category selector + paste/upload box → the identical 🚩/✅/❓ result. *"Kept simple at first"* refers only to the surrounding UX (no accounts, no history/alerts, minimal shell), **not** a weaker analysis.

> **Single source of truth:** the **check logic and output are identical on Telegram and web**, because both clients call the one backend (intake → OCR → rules + LLM → graph → output). **No analysis logic ever lives in a client.** The clients differ *only* in (a) identity-bound features — history, alerts, and report attribution are Telegram-first while web is anonymous in v1 — and (b) client-specific UX (buttons vs. a web form).

> **v1 web scope (post-review, 2026-06-17):** the web client ships the **text check + quick lookup + a deep-link to the bot**. Anonymous **image upload sits behind captcha + tight limits**, and anonymous **reporting is deferred to Telegram** — image upload and reporting are the real abuse/legal vectors. The *analysis* stays identical to Telegram's; the gating is on risky *inputs/flows*, not on check quality.

**Consequence to budget for:** an open web endpoint has no free anti-spam. Abuse handling (rate-limit, captcha, upload limits) is therefore a **v1 task**, not "later."

---

## 8a. Analysis engine — hybrid: LLM + rule checklist ✅

Every analysis runs a deterministic rule layer **and** an LLM layer, then merges them. Detection of known scams must never depend on LLM mood. (This is the "AI orchestration" box in the diagram above.)

**1. Rule layer (hardcoded checklist, runs first).** A curated, versioned library of red-flag rules **per category**, each firing on extracted/normalized signals and mapping to a specific message. Examples:
- *Account & identity (primary):* handle or phone already appears in prior reports · one phone number linked to multiple accounts in the graph · display name ≠ username · stock/stolen profile photo. **Only from user-submitted screenshots/evidence (NOT auto-derivable — see API note below):** account brand-new / recently renamed · username recently changed · few/no posts or history.
- *Seller / listing:* price far below market · product photo is a known reused image (perceptual-hash hit) · pushes to move off-platform immediately · refuses video call / meeting / escrow.
- *Payment:* full prepayment before meeting · push to a personal card/transfer · pressure/urgency · "pay via gift card / crypto / top-up" · card or phone matches a graph report. *(Card kept as a supporting signal only — BIN + last4 + hash, never the full number.)*
- *Job offer:* upfront "deposit"/fee · unrealistic salary · documents/payment requested too early.
- *Investment:* guaranteed returns · referral/MLM structure · urgency to act now.

Rules are **deterministic, unit-testable, and multilingual** (UZ + RU keyword sets). They guarantee the obvious signals are *never* missed.

> **Telegram API reality (corrected 2026-06-17):** the bot sees the *victim's* user object, not the scammer's. **Account age and rename history are not in the Bot API**; usernames are optional; a forwarded message's origin can be hidden (`MessageOriginHiddenUser`). So account-age / rename / post-count red flags must come from **user-submitted screenshots or descriptions** — never auto-derived from the API. *(Re-verify against current Bot API docs before building.)*

**2. LLM layer.** Receives the original text/OCR + extracted entities + the rule-layer hits, and: catches nuanced/novel red flags the rules miss, writes the natural-language output in the user's language (UZ/RU), and generates the **✅ verify** and **❓ ask** parts. Hard constraints in the prompt: **never output a score or a safe/unsafe verdict**, and stay grounded in the provided signals (no invented facts).

**3. Merge + format.** Combine rule hits + LLM findings + graph evidence into the fixed 🚩/✅/❓ block; dedupe. **Rule hits and graph evidence are authoritative; the LLM polishes and extends, never overrides them.**

**Strategic note:** the rule library is a locally-tuned asset (CA/Uzbek-specific scam patterns) that — like the graph — a generic AI clone doesn't have. Keep it as **editable config/data, not buried in code**, so rules can be added without a redeploy.

---

## 8b. Entity model & priorities ✅

*(Set 2026-06-17.)* The graph centers on **persistent scammer identity**, not on burnable payment instruments. A scammer rotates cards freely but reuses handles and phones across victims, so identity is what actually links scams together.

**Primary entities (the spine — extract & link these first):**
- **Telegram** — username, user ID (where available), group/channel name.
- **Instagram** — handle / profile name.
- **Phone number** — normalized (E.164).

**Scammer cluster ("scammer profile"):** a node linking the identifiers believed to belong to **one actor** — connected via shared phone, shared handle, reused photos, or co-occurrence in reports. This cluster *is* the fraud-intelligence asset; lookups and evidence resolve against it.

**Scam-pattern tags (modus operandi):** every report/cluster is tagged with a playbook — e.g. *prepayment-then-disappear · fake delivery · fake payment screenshot · job-deposit · investment/MLM · OTP/phishing · stolen-account resale*. Powers pattern-level evidence and future analytics.

**Supporting entities (kept, but not the spine):**
- Listing / profile URL
- Product or profile photo (perceptual hash)
- **Card number — BIN + last4 + hash only, never the full PAN.** A secondary corroborating signal.
- Repeated scam phrases

**Why this ordering:** identity entities link scams far better than rotated cards, *and* de-emphasizing card data shrinks the regulatory/liability surface — exactly what the fundability review (data-localization / Personal Data Law) called for. Two wins from one decision.

---

## 8c. Report trust model — states & independence ✅

*(Added 2026-06-17.)* This is the heart of trust, so it is defined precisely — a vague "N reports" invites poisoning.

**Report / claim states:**
- `unreviewed` — submitted, not yet corroborated or reviewed.
- `corroborated` — ≥ N *independent* reports agree (automatic).
- `verified` — confirmed by admin review (high-impact) or strong evidence.
- `disputed` — contested by the subject or others; under review; shown with a dispute flag.
- `cleared` *(a.k.a. dismissed)* — found false/insufficient; no longer shown as a negative signal.
- `imported` — seed data from public lists/partners; informative, **never** shown as 'verified.'

Only `corroborated` and `verified` surface to other users as evidence. `unreviewed` / `imported` may appear only with explicit weaker framing (*"1 unverified report"*, *"imported from a public list"*).

**"Independent" — all must hold (else the reports count as ONE signal, not many):**
- different Telegram users (distinct IDs),
- different report times (not a single burst),
- different evidence (no duplicate / near-duplicate screenshot — perceptual-hash check),
- no obvious referral/abuse link between reporters,
- no shared device/IP signal (web).

**What a count means (define before building the query):**
- **A check is not a report.** A *check/lookup* silently creates or touches entity nodes with **zero negative weight** (§8d) — only a **report** adds a negative signal. Lookups must never inflate "reported N×," or we mislead users and recreate the liability we set out to avoid.
- **"Reported N× this month" counts only `corroborated` + `verified` reports**, over a **rolling 30-day window**. Older reports still exist, but the headline number is recent-weighted. `unreviewed` / `imported` never feed the headline count — they may appear only with explicit weaker framing.

**Reporter trust-weight (re-instated from the original brief):** every reporter carries a `trust_score` + report-quality stats, and a report's contribution to corroboration is **weighted by reporter trust** — so one bad actor, or a ring of fresh accounts, can't manufacture "N independent reports." New / low-trust reporters count for less until they build history. This is the cheapest, strongest anti-brigading lever.

**Two-sided abuse defense:** the threat is not only flooding *false reports* against a victim, but also a scammer **mass-disputing his own record** or **filing retaliatory reports against a competitor / innocent**. Reports and disputes are both rate-limited, evidence-gated, and trust-weighted; high-impact actions in either direction route to admin review (§8f, US-2.4).

---

## 8d. Entity extraction & normalization spec ✅

*(Added 2026-06-20.)* The moat is only as good as extraction — so the **producer of graph data is specified before the schema that stores it.** Every check and report runs the same extraction → normalization pipeline; its output is what the graph persists.

**Per-entity rules:**
- **Phone** → normalize to **E.164**. Handle UZ formats: `+998 XX XXX XX XX`, bare 9-digit local, spaced / dashed / parenthesized, and masked inputs. Store the normalized value as the canonical key; keep the raw as-seen for audit.
- **Telegram** → distinguish `@username` · display name (not unique — *not* a key) · `t.me/…` link · forwarded-message origin. **Forwarded origin can be hidden** (`MessageOriginHiddenUser`) — when hidden, capture nothing rather than guess. Username is the key where present; user ID where the API exposes it.
- **Instagram** → canonicalize the handle (strip `@`, URL, trailing slash; case-fold).
- **Card** → split to **`BIN + last4 + SHA256(full)`** at the moment of extraction; **the full PAN is never stored or logged** (§11a).
- **Listing / profile URL, product / profile photo (perceptual hash), repeated scam phrases** → supporting entities (§8b).

**Cross-cutting:**
- Each extracted entity carries an **extraction-confidence** and a **source** (typed-by-user · OCR · forwarded · link-parsed). Low-confidence entities are stored but flagged and do **not** auto-corroborate.
- **Canonicalization & dedupe:** the normalized value is the unique key per entity type; near-duplicates collapse to one node.
- **Multilingual:** extraction and the rule keyword sets run for RU, UZ-Latin, and UZ-Cyrillic (§7).

---

## 8e. Cluster governance — merge & unmerge ✅

*(Added 2026-06-20.)* The scammer cluster (§8b) is the asset, but **blind auto-merge is a defamation risk**: a shared money-mule card, a recycled phone, or a victim's mistyped number can fuse an innocent person into a scammer cluster.

- **Conservative by default.** v1 **auto-merges only on a strong identity match** (e.g. same Telegram user ID, or same normalized phone *plus* a second corroborating identifier). Weaker signals (a single shared card, one reused photo) **propose** a merge to the admin queue — they don't execute it.
- **Always reversible.** Every merge is **unmergeable**; clusters keep **per-edge provenance** (which report/check created each link, when, with what confidence) so a wrong link can be cut without losing the rest.
- **Disputes split, not blanket-clear.** A successful dispute (§8f) on one identifier must not silently taint the others — unmerge that edge, don't clear the whole cluster.
- Cluster changes are **audit-logged** (who / when / why).

---

## 8f. Dispute & removal flow ✅

*(Added 2026-06-20.)* A system that stores accusations must let the accused contest them — both a legal requirement (§11a) and the core defamation defense. The `disputed` / `cleared` states (§8c) need an actual **flow**:

1. **Discovery.** We publish **no public accusation pages** (§12), so a subject can't "find their page." Instead: a **`/dispute` command** plus a **published contact channel** (bot + email), stated in the privacy notice (§9, §11a). Someone who learns a claim was made about them (e.g. a buyer cited it) can open a dispute by submitting the identifier in question.
2. **Intake.** Collect the disputed identifier, the claim, and any counter-evidence. The identifier is marked **`disputed`** and **suppressed as a negative signal while under review.**
3. **Adjudication.** Admin reviews against the report evidence (US-5.1). Outcome: **`cleared`** (no longer shown as negative; cluster edge cut per §8e) or dispute rejected (with a logged reason). Target a stated **SLA** (e.g. review within N days).
4. **Anti-abuse.** Disputes are **rate-limited and trust-weighted** (§8c) so a scammer can't self-clear by spamming disputes; repeated bad-faith disputes lower the disputer's trust.
5. **Web is anonymous (v1)** → disputes are **Telegram / email-first** (an anonymous web user can't be notified of the outcome).

---

## 9. Core user flow (Telegram)

1. `/start` → language auto-detected → a **one-time consent / privacy notice** is shown (what we store, why, retention, how to dispute — §11a); consent version + timestamp are recorded before any data is processed.
2. Bot: *"Nimani tekshiramiz? / Что проверяем?"* → user taps **Payment**.
3. Bot: *"Send the screenshot, card/phone, or describe what happened."*
4. User sends a payment screenshot + *"просит предоплату на эту карту."*
5. Backend: OCR → extract entities → AI analysis + graph lookup.
6. Bot returns the 🚩/✅/❓ block + any graph evidence line.
7. Bot: *"Did this turn out to be a scam? [Yes / No / Not sure]"* → optional report → feeds the graph.

Web checker mirrors this as a single page.

---

## 10. Usage limits & abuse 🔶

**Recommended model (supersedes the initial "flat 3/day" idea):** separate cheap from expensive operations, and **soft-degrade instead of hard-blocking.**

- **Graph lookup** (is the entity already known?) = cheap/instant → effectively unlimited.
- **AI analysis + OCR** (the written read) = the costly part → this is what's limited.

| Client | Free AI checks/day | Abuse control |
|---|---|---|
| **Telegram** (identified user) | ~10 | built-in anti-spam |
| **Web** (anonymous) | ~3–5 | captcha after first few; upload size limits |

- **Over the limit → don't block.** Still return the free graph lookup ("you've used today's full reads"), so the user always gets *something* and we keep collecting entities/reports.
- **Cache the AI write-up, never the graph result.** Cache identical inputs (~48h) so the LLM isn't re-billed — but **always re-run the live graph lookup**, because an entity reported within those 48h would otherwise return a stale "no records" (now actively harmful).
- **Quick-lookup is rate-limited too.** It doesn't consume the AI limit, but an anonymous "is this phone / card known?" endpoint is an **enumeration oracle** — abusable to probe whether a specific identifier is in the DB (e.g. a scammer checking whether he's been reported). Rate-limit it per user / IP, and keep answers **aggregate** (*"reported N×"*) — never expose report contents or reporter identity.
- **Log cost-per-check from day 1** and tune these numbers against the real bill — don't over-optimize before there's data.

---

## 11. Monetization ✅ / 🔶

- **v1: no payment in the product.** ❌ No subscriptions, no paywall.
- **Later in MVP (optional): donations** as a **cost-offset only** — Telegram Stars or a simple Payme/Click link / card number. 🔶
  - ⚠️ **Honest caveat:** donations are a tip jar, not a business model and **not** the fundraising story. The real future revenue is the **B2B fraud-intelligence API** (marketplaces, fintechs/banks, platforms) — out of scope for v1 but the reason the graph exists.
- **Validate B2B *in parallel* with v1 (not "later"):** interview ~5 prospective buyers — marketplaces, fintechs/banks, high-volume Telegram sellers — to learn what they'd actually pay for (real-time API, batch checks, fraud digest, seller watchlist, investigation dashboard). A signed design-partner / LOI is the single biggest fundability unlock.

---

## 11a. Privacy & data-protection spec (launch blocker) ✅

*(Added 2026-06-17.)* This product handles phones, social identities, card fragments, screenshots, and *accusations* — so privacy is a product spec, not a footnote. Uzbekistan's personal-data law ties collection/storage to a stated purpose + retention period, grants subjects access/consent rights, and restricts cross-border transfer. *(Not legal advice — review with a local lawyer before launch; treat the items below as launch blockers.)*

1. **Local storage by default** — data on servers in Uzbekistan.
2. **Redact PII before *any* external call — LLM and OCR alike.** Strip full card numbers and minimize identifiers before a third-party/foreign LLM call. **Cloud OCR is the same cross-border transfer** — it sees the raw screenshot (full cards, faces) *first* — so either run OCR **locally / on-prem**, or treat its output as PII and redact before anything leaves the country. *A foreign LLM/OCR API = cross-border transfer of personal data — a legal risk; local processing + redaction is the mitigation, and it constrains the stack (§14).*
3. **Card data** — BIN + last4 + hash only, never the full PAN.
4. **Raw screenshots stored only for *reports*** (as evidence), not for ephemeral checks — a check extracts entities, then **discards the image immediately after extraction.** On upload, **strip EXIF / GPS metadata**; assume screenshots may contain **third-party faces / data** — minimize, and never retain them for non-report checks.
5. **Explicit retention rules** per data type (ephemeral check inputs deleted within X days; report evidence retained only while the report is active).
6. **Dispute / removal flow from day 1** — a subject can contest or request removal of a claim about them (ties to the `disputed` / `cleared` states). Both compliance *and* your defamation defense.
7. **No public accusation pages** — results go privately to the person who checked; we never publish indexable "X is a scammer" pages (also a non-goal, Section 12). Public accusations are the single biggest defamation surface.

---

## 12. Explicit non-goals (NOT in v1) ❌

- Risk scores / "safe" badges (liability).
- B2B API, subscriptions, in-product payments.
- Seller trust pages / verified profiles.
- Public / shareable entity report pages (defamation + privacy landmine).
- Large-scale scraping or channel monitoring.
- ML graph clustering — v1 stores edges and does **exact-match** lookups only.
- Other countries. **Uzbekistan only.**

---

## 13. Success metric 🔶

**Primary (proposed):** *% of users who run a 2nd check within 14 days* — repeat use, not one-time curiosity.

**Real-impact metric:** *# of users who confirm they avoided a payment* because of a check — the outcome that matters most, and the strongest fundraising line.

**Health of the data engine & moat:**
- **entity-extraction rate** — % of checks yielding ≥1 graph entity (guards against becoming an AI wrapper),
- **graph-match rate**, trending over time (the moat made visible),
- **report completion rate** + **verified reports / week** (data quality & volume),
- **dispute rate** (trust + legal health),
- **cost per AI check** (unit economics),
- **share rate** (virality).

---

## 14. Open decisions (still to lock before/while building)

1. ~~**AI reliability approach**~~ ✅ **LOCKED** → hybrid: **LLM + hardcoded per-category red-flag checklist** (see Section 8a).
2. **Confirm usage-limit numbers** (Section 10).
3. **Confirm the primary success metric** (Section 13).
4. **Tech stack** — Telegram framework; **OCR (RU + UZ Latin/Cyrillic; prefer local / on-prem for privacy, §11a)**; **LLM provider (redaction-friendly / regionally hostable, §11a)**; **database — relational is enough: exact-match edges only (§12), no graph DB required for v1**; web framework; **UZ hosting**. → Architecture phase; note the privacy spec (§11a) constrains these choices.
5. **Reconcile the two data-model sources when writing the schema** — the original brief's concrete tables (`intial.md`: `identifiers / reports / users / checks / disputes` with trust fields) **plus** the PM-doc additions (state machine §8c, cluster §8b/§8e, `imported` label, extraction fields §8d, retention/consent fields §11a). The schema is the **union**, not a choice between them.

---

## 15. Top traps to avoid (carry-over from strategy)

- Reintroducing a numeric risk score or "this is safe" output.
- Building the consumer product twice (Telegram + web) instead of one shared backend.
- Treating donations as the business model in investor conversations.
- Launching the web endpoint without abuse/rate-limiting.
- Letting the graph stay empty because reports are too hard to submit.

---

## 16. Finalized v1 function list ✅

*(Decided via PM review, 2026-06-17 — all on the recommended path. In scope for v1 unless marked deferred.)*

### A. Core check
1. **Guided check** — category select (`Payment`/`Seller`/`Job offer`/`Investment`/`Other`) → freeform text + image upload → hybrid analysis (rules + LLM) → fixed 🚩/✅/❓ output + graph evidence line.
2. **Quick entity lookup** — paste only a card/phone/username → instant graph answer (*"reported N×"* / *"not known"*), no AI write-up, **does not consume the AI daily limit**.

### B. Data & trust loop
3. **Standalone scam report** — dedicated "Report a scam" flow; submit a scammer's card/phone/username/screenshots *without* running a check first.
4. **Post-check report prompt** — *"Did this turn out to be a scam? [Yes/No/Not sure]"* after every check.
5. **Report moderation** — low-stakes reports surface automatically after **N independent corroborating reports** (independence + states defined in **Section 8c**); high-impact reports (a specific named person/business) are held in an **admin review queue** first. The defense against false reports / poisoning.
6. **Graph evidence display** — when an entity matches, show evidence (*"reported 2× this month"*) — never a verdict.
7. **Silent capture** — every check/report extracts + normalizes entities and stores **perceptual image hashes** from day 1. (Reused-photo *matching* deferred until a corpus exists.)

### C. Retention & growth
8. **Share result + invite** — "Share" button forwards a clean summary + a bot deep-link (warn a friend = recruit them).
9. **Watch + notify** — if an entity a user checked later crosses the report threshold, the bot proactively alerts them. *(Telegram-only — needs identity.)*
10. **Recent-checks history** — `/history` of the user's recent checks/results. *(Telegram-only — needs identity.)*
11. **Contextual education** — short, 1-tap *"how this scam usually works"* tips, surfaced by category.

### D. Cross-cutting
12. **Languages** — UZ + RU auto-detect; reply in the same language.
13. **Usage limits & abuse** — soft-degrade model (Section 10): unlimited cheap lookups, limited AI checks, input caching, web captcha + rate-limits.

### E. Admin (internal web dashboard)
14. **Report review queue** — approve/reject high-impact reports.
15. **Entity / graph management** — view, merge, correct entities & edges.
16. **Rule library editor** — add/edit per-category red-flag rules as **config, no redeploy**.
17. **Abuse controls** — rate-limit / ban users, inspect abuse signals.
18. **Metrics dashboard** — checks, graph-match rate, report volume, cost-per-check.

### Client matrix — what each UI exposes in v1

| Function | Telegram | Web (v1) |
|---|---|---|
| Guided check | ✅ | ✅ (text; image upload behind captcha/limits) |
| Quick entity lookup | ✅ | ✅ |
| Standalone report | ✅ | ❌ deferred to Telegram (abuse/legal vector) |
| Post-check prompt | ✅ | ✅ |
| Graph evidence | ✅ | ✅ |
| Share + invite | ✅ | ✅ |
| Watch + notify | ✅ | ❌ (no identity) |
| Check history | ✅ | ❌ (no identity) |
| Education tips | ✅ | ✅ |

**Identity note:** history, alerts, and reliable report attribution need a stable identity. Telegram provides it for free; the web client is **anonymous in v1**, so those functions are **Telegram-first**. Web accounts (which would unlock them on web) are **deferred**.

---

## 17. Build order — full scope, phased ✅

*(Added 2026-06-20. Scope is the full §16 list; this is the **order**, so a solo build ships something usable at each step instead of everything-or-nothing.)*

| Milestone | Ships | Proves |
|---|---|---|
| **M1 — Core loop** | Entity extraction/normalization (§8d) · rules + LLM (§8a) · relational graph store · guided check + quick lookup + post-check prompt + standalone report | The wedge works **and** the graph starts filling (the moat) |
| **M2 — Trust** | Report-state machine + independence + reporter trust-weight (§8c) · cluster governance (§8e) · admin review queue · dispute / removal flow (§8f) | The data is trustworthy and defensible (legal + anti-poison) |
| **M3 — Growth (Telegram)** | Share + invite · watch + notify · `/history` · contextual education | Retention + virality |
| **M4 — Web client** | Text check + quick lookup + deep-link, behind captcha / limits | Reach beyond Telegram — **after** the core is proven |
| **M5 — Admin polish** | Cluster-management UI · rule-library editor UI · abuse-control UI · metrics dashboard | Operability at scale |

**Parallel, non-engineering — start at M1, not after:** graph **seeding** (§3b), **B2B discovery** interviews (§11), **legal consult** (§11a — *before* the schema hardens), and **content authoring** (§18). These gate fundability and data quality and won't happen if left to "later."

---

## 18. Content & ops workstreams (not code) ✅

*(Added 2026-06-20.)* Three deliverables are **content assets**, not features — authored in **RU + UZ (Latin & Cyrillic)**, per category, kept fresh, each with a named owner and a refresh cadence:

1. **Rule library** (§8a) — the per-category red-flag checklist + keyword sets (the locally-tuned moat asset).
2. **Education tips** (§16 #11) — the 1-tap "how this scam works" explainers.
3. **Seed data** (§3b) — curated public reports + partner-shared history, labelled `imported`.

Treated as code, these rot. Assign owner + cadence now.
