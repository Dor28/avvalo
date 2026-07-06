# Avvalo — Product Horizons: the 3-year option map

> **Status:** Strategic option map (discussion output) · 2026-07-04
> **Owner:** Solo technical founder (Uzbekistan)
> **What this is:** the ranked map of *future* opportunities in the trust/anti-fraud direction — where "good for people" and "good startup" intersect, with new-technology angles. These are **options, not a to-do list**; the current sequence in [PRODUCT_VISION.md](PRODUCT_VISION.md) §4 (launch → content flywheel → merchant gate) is unchanged and outranks everything here.
> **Reads with:** [PRODUCT_VISION.md](PRODUCT_VISION.md) (the 90-day plan this extends), [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) (safety principles — they win on any conflict), [ADJACENT_PRODUCT_IDEAS.md](archive/ADJACENT_PRODUCT_IDEAS.md) (the 2026-06-21 idea generation this supersedes as the forward-looking backlog).

Legend: ★ = strength score used in §6 · ⚖️ = needs counsel confirmation before build

---

## 1. Two framing principles (read before the ideas)

**1. The person you protect and the person who pays are almost never the same person.**
Every idea below protects consumers, employees, or group members — and charges businesses, banks, platforms, or grant-makers. Every safety product that tries to charge the scared person directly dies of episodic usage. This is the unifying commercial shape of the whole map.

**2. Verify situations and artifacts — never persons.**
The pivot rule from [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) §1 applies to every future product. Companies, domains, channels, listings, documents, and messages are fair game for lookups and verdicts; identifiable people are permanently not. ⚖️ One UZ-specific nuance to confirm with counsel: many merchants are **individual entrepreneurs (YaTT / self-employed)** whose business data may legally count as *personal* data — any company-verification feature needs a ruling on where that line sits.

---

## 2. The tailwind: AI industrialized scamming

New technology created the market moment this map exploits:

- **Voice cloning** — "mom, I'm in trouble" calls in the victim's relative's actual voice.
- **Deepfake video** — fake video circles and celebrity/official endorsements pushing investment scams on Telegram.
- **LLM-written phishing** — grammatically perfect Uzbek scam copy at scale, for the first time ever.
- **Generated artifacts** — fake payment screenshots, fake listings, fake documents in seconds.

Scam volume *and* quality are rising globally and will hit UZ/CA with a lag — Avvalo is building the antibody at the moment the virus mutates. Regulation follows the damage: the UK and Australia already force banks to act on authorized-push-payment scams; when UZ's central bank copies that playbook, **regulation creates budgets** — and Tier 2 below is positioned to sell into them.

---

## 3. Tier 1 — natural engine extensions (solo-feasible, ~2026)

### 3.1 Voice-message checks ★ next after launch

**Concept.** Accept a forwarded Telegram voice message → speech-to-text → the *same* engine (rules + LLM + validator) → the same 🚩/✅/❓ output.

**Why it matters for people.** Uzbekistan runs on Telegram voice messages, and elders — the mission's core users — barely type. Voice is also the entry into the voice-cloning era: the durable product is **not** deepfake *detection* (an arms race a solo founder loses) but coaching the **verification protocol** — hang up, call back on the known number, ask the family question only the real person knows.

**Startup case.** Deepens the consumer wedge and the brand story ("protecting grandmothers from AI voice scams" — a fundable sentence); voice scenarios feed the training product (§3.3).

**Build notes.** aiogram already receives voice; the delta is an STT provider stage before `run_check()` plus a "voice scam" rule family. **The one real unknown is Uzbek STT quality** — run an eval (like `tools/eval_models.py` did for LLMs) before committing. PII rule: transcripts go through the existing minimizer; audio is discarded after transcription like images are.

**Honest caveats.** STT cost raises cost-per-check — re-verify the $0.03 ceiling or set a separate voice ceiling. Uzbek dialect/code-switching (UZ+RU mixed speech is the norm) may degrade transcription; degrade gracefully to "couldn't understand — describe it in text."

### 3.2 Agentic verification — the assistant that *does* the checking ★ the next big product bet

**Concept.** Today Avvalo says "here's what to verify." The agentic version verifies it live: is this company in the state registry? Was this domain registered six days ago (WHOIS)? Is this Telegram channel two weeks old? Do these product photos appear on other listings (reverse image search)? Output: *"I checked 4 things; here's what I found and what I couldn't confirm."*

**Why it matters for people.** The users who most need protection are precisely the ones who can't follow a checklist. Doing the verification for them is a 10× usefulness jump.

**Startup case.** Moves the product from advice to **verification-as-a-service** — real willingness-to-pay territory (consumers via limits, merchants via the paid face) and real defensibility (data-source integrations, not just prompts). This is also the **legal resurrection of the "lookup" dream**: the retired accusation graph looked up *persons*; this looks up *companies, domains, channels, and artifacts*.

**Build notes.** A tool-using stage in the pipeline after rules, before the LLM write-up; each verification is a typed tool with its own timeout and confidence. Candidate sources: company registry data (orginfo.uz-style), WHOIS/domain age, t.me channel metadata, reverse image APIs. Cost/latency budget per check must be set up front (agents can 5× a check's cost if unbounded).

**Honest caveats.** v1 scope explicitly excluded "URL browsing / external reputation lookup" — this is a deliberate **v2 decision**, not scope creep by accident. Some sources need scraping or licensing. ⚖️ The YaTT personal-data nuance (§1) applies to company checks. Findings must be reported as facts with sources, never fused into a verdict.

### 3.3 Scam-awareness training for organizations — "KnowBe4 for Central Asia" ★ fastest second revenue line

**Concept.** Security-awareness training localized for UZ/RU: a training bot that sends employees (or family members, or students) realistic simulated scam scenarios, quizzes them, and gives the owner/HR a completion-and-failure dashboard.

**Why it matters for people.** Prevention beats detection; simulation beats lecture. Fresh, local scenarios ("this month's fake-delivery scam") train reflexes generic courses can't.

**Startup case.** Security-awareness training is a proven, boring, billion-dollar global B2B category (KnowBe4 et al.) with **zero Uzbek-language localized players**. Payers: SMBs (staff handling payments), banks (must train staff *and* fund customer-awareness campaigns — the sponsorship hypothesis finally gets a concrete product), schools/universities via grants. Differentiator no incumbent can copy: the **Scam Pulse** feeds fresh scenarios monthly, straight from live check data.

**Build notes.** Reuses: rule families → scenario templates, curated stories → case studies, the bot infra → delivery channel. Net-new: scenario packs, a quiz flow, an org admin surface (start as a CLI/report like the metrics export), per-seat billing later.

**Honest caveats.** This is a *sales* product — pilots come from the same interview muscle as the merchant gate, so it competes for founder time with Avvalo Merchants discovery. Don't run both B2B motions simultaneously; sequence on evidence.

### 3.4 Pattern-similarity evidence — "matches a known circulating scam" ★ the ML flagship (added 2026-07-06 from [ML_RESEARCH.md](ML_RESEARCH.md))

**Concept.** Embed the curated opt-in story corpus; at check time, cosine-match the minimized text and, on a strong match, add an evidence line: *"This message is highly similar to the fake-delivery scam circulating since June (matched against N community-donated examples)."*

**Why it matters.** It legally resurrects the emotional power of the retired "reported N×" line — it matches **patterns (text), never people**. Every donated story visibly protects the next user, which supercharges the story-donation loop.

**Build notes.** pgvector on the existing Postgres + one multilingual-embedding call per check (~$0.0001); threshold tuned against golden fixtures; the line is rendered as pattern evidence, never as a claim about a sender. Production-proven approach in phishing detection (sources in [ML_RESEARCH.md](ML_RESEARCH.md) §3).

**Gate.** ~100 founder-reviewed corpus examples (R3 output). No training required — this is retrieval, not fine-tuning.

---

## 4. Tier 2 — partnership-gated (the venture-scale story)

### 4.1 Pre-payment context API for banks & payment apps ★★ the rung-3 flagship

**Concept.** A privacy-safe risk signal at the payment moment: "this recipient/context matches a fake-shop pattern circulating this month."

**The structural insight.** When a victim *authorizes* a scam payment, the bank sees a completely normal transaction — the evidence of fraud lives in the **conversation**, which only Avvalo sees. Banks and payment apps literally cannot build this signal without Avvalo's side of the data. That asymmetry is the whole pitch.

**Why it matters for people.** Stops the loss at the last possible moment, at population scale, inside apps people already use.

**Startup case.** This is where the aggregate data asset becomes recurring B2B revenue, and the story that makes regional VCs lean in ("trust layer for informal commerce"). Regulatory tailwind: as APP-scam liability rules spread (UK/AU precedents), banks acquire budgets for exactly this.

**Prerequisites (hard).** Consumer traction (the signal is only as good as check volume) · privacy design reviewed by counsel (aggregate patterns only — no per-person data leaves) ⚖️ · one payment-provider or bank design partner. Do not pitch this before the Pulse exists and merchant evidence is in.

### 4.2 Group Guard — passive protection for Telegram groups & channels ★ best protection-per-effort

**Concept.** Add [@Avvalo_official_bot](https://t.me/Avvalo_official_bot) as a group/channel admin; it screens incoming messages with the shared engine, removes scam links/phishing/spam, and CAPTCHA-gates new joiners. Already sketched in [ADJACENT_PRODUCT_IDEAS.md](archive/ADJACENT_PRODUCT_IDEAS.md) §13 / [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) §17.

**Why it matters for people.** One install protects thousands — the highest protection-per-effort ratio on this map.

**Startup case.** B2B2C distribution: every admin who installs it is a distributor; large channels are future sponsorship inventory. Freemium (small groups free, big communities paid).

**Honest caveats.** Flips the model from *user-initiated checks* to **passive monitoring** — needs its own install-time privacy notice, a conservative default (flag > delete), an admin appeal path, and false-positive discipline; moderation mistakes in big groups are public. Infra cost scales with message volume, not users — model it before launch.

---

## 5. Tier 3 — horizon (right cause, wrong year)

### 5.1 JobPass — migrant-worker protection (impact-funded)

Job/visa/recruiter-fee scam checks for Uzbekistan's millions of labor migrants. Enormous human impact; weak commercial payer (workers can't pay, recruiters won't) — but a **magnet for impact funding**: IOM, World Bank, and labor-migration NGOs fund exactly this kind of digital tool. Park until Avvalo wants a grant-funded expansion track; the engine reuses as-is with a job-offer rule pack (partially exists in the family pack already).

### 5.2 A small self-hosted Uzbek scam-classification model ("sovereign AI") — *detailed in [ML_RESEARCH.md](ML_RESEARCH.md)*

Fine-tune a small classifier on Avvalo's own labeled corpus (opt-in stories + minimized examples) for cheaper, faster, in-country first-pass detection. **Not now:** the corpus doesn't exist yet, and prior research (2026-06-21) showed community Uzbek fine-tunes perform near-random — so this is a *narrow classifier on our own data* play, never a general-model play. When real: a strong IT Park / government narrative ("data never leaves Uzbekistan") and a genuine cost/latency win. **Gate (revised 2026-07-06 per [ML_RESEARCH.md](ML_RESEARCH.md) §2):** a SetFit-style classifier on an Uzbek encoder (UzBERT/BERTbek) becomes credible at **~300–500 reviewed examples** (+ LLM-distilled labels); the full self-hosted "sovereign model" story still wants a few thousand.

### 5.3 Escrow / safe-deal — the endgame, via partnership

The actual cure for prepayment fraud is holding the money until delivery. Building it means regulated fintech: licenses, capital, float management — wrong scale for a solo founder. The realistic version: Avvalo as the **trust/verification layer inside someone else's escrow** (Uzum, Payme, Click). Keep as the north-star answer to "where does this end up," not as a roadmap item.

---

## 6. Scoring & pull-forward criteria

| Idea | Good for people | Startup strength | Solo-feasible now | When |
|---|---|---|---|---|
| 3.1 Voice checks | ★★★ | ★★ | Yes | After launch |
| 3.2 Agentic verification | ★★★ | ★★★ | Mostly | Next big product bet |
| 3.3 Training (KnowBe4-CA) | ★★ | ★★★ | Yes | Once the content flywheel runs |
| 3.4 Pattern-similarity evidence | ★★★ | ★★★ | Yes | At ~100 reviewed stories |
| 4.1 Payment-context API | ★★★ | ★★★★ | No — needs traction | After merchant proof + Pulse |
| 4.2 Group Guard | ★★★ | ★★ | Yes | Opportunistic |
| 5.1 JobPass | ★★★★ | ★ | Grant-dependent | Horizon |
| 5.2 Sovereign model | ★★ | ★★ | No — needs corpus | Horizon |
| 5.3 Escrow | ★★★★ | ★★★ | No — regulated | Endgame via partnership |

**An idea may be pulled forward only if all four hold:**
1. **Reuses the engine** (intake → OCR/STT → minimize → rules → LLM → validate) rather than forking it.
2. **Has a nameable payer** — a person or institution you can interview this month.
3. **Verifies situations/artifacts, never persons** (§1, and PRODUCT_GUIDE §14 non-goals).
4. **Capacity exists** — launch is done and the merchant gate is resolved or the idea provably doesn't compete with it for founder time.

**Standing discipline:** the [PRODUCT_VISION.md](PRODUCT_VISION.md) §4 sequence (deploy → channel + scam library → story capture + Pulse → alpha → merchant go/no-go) is the current plan of record. This document is where good ideas wait without dying — and without derailing the one thing that matters now: shipping.

---

## 7. The ranked feature shortlist (senior-PM picks, founder discussion 2026-07-04)

The order I would build in if it were my product — merging the §4 near-term plan of [PRODUCT_VISION.md](PRODUCT_VISION.md) with this map. Effort assumes the existing engine; none of these fork it.

### Build now, in this order (0–60 days)

| # | Feature | Why it wins | Effort |
|---|---|---|---|
| 1 | **"Forward this warning" button** on every check result (bot deep-link attached) | A scared user's first instinct is to warn someone — the only zero-effort viral loop; was in the original design | ~0.5 day |
| 2 | **Scam library** — 7 public pages, one per rule family in `rules/family/families.yaml` | Makes Avvalo findable (no UZ-language scam content hub exists); every page funnels into the checker | ~1–2 days code + content |
| 3 | **Opt-in story capture** → minimizer → operator review → publish | Emotional fuel for the channel, proof-of-impact for the grant, seed of the labeled UZ corpus | ~2–3 days |
| 4 | **Scam Pulse** — monthly aggregate of `check_event.rule_ids` by language/face | Turns already-collected data into authority: PR, sponsor pitch, IT Park evidence | ~1 day + monthly ritual |
| 5 | **Voice-message checks** (STT → same engine) | Biggest usefulness jump for the core audience (voice-note culture, elders); entry into the voice-clone era | gate: UZ STT eval first (§3.1) |
| 6 | **URL reputation stage** — check extracted links against Google Safe Browsing + URLhaus + OpenPhish, plus our own UZ phishing list | Free feeds, 15–30% fewer misses when combined; the UZ list becomes a unique data asset ([ML_RESEARCH.md](ML_RESEARCH.md) §4) | ~2–3 days (ROADMAP R6) |

### The big bets after launch/traction

| # | Feature | Trigger |
|---|---|---|
| 7 | **Pattern-similarity evidence** (§3.4) — "matches a known circulating scam," retrieval over the story corpus | ~100 reviewed R3 stories |
| 8 | **Agentic verification** (§3.2) — domain age, company registry, channel age, reused photos: advice → verification | After launch stabilizes; cost/latency budget set |
| 9 | **Merchant team workflow** — prediction: the paying feature is *policy + audit log* ("goods don't ship until the checklist passes; owner sees who approved"), not fancier forensics — plus deterministic **OCR field cross-checks** on receipts (amount/date/name vs order), NOT pixel forensics | Only what the 20 interviews demand; billing only after 3 dated paid pilots |

### The do-not list

- ❌ Open forum (moderation load + defamation surface; the channel with comments is the forum for now).
- ❌ Person/phone/card lookup — permanently.
- ❌ Mobile app, Deal Check, new faces, payments infrastructure — all premature before the merchant gate resolves.
- ❌ *(added 2026-07-06, evidence in [ML_RESEARCH.md](ML_RESEARCH.md) §5–§7)*: **"fake screenshot detector" verdicts** (Telegram recompression breaks ELA forensics; hints only), **audio-deepfake detection claims** (~78% real-world accuracy with false positives), **federated learning / differential-privacy training** (wrong scale; consent + minimization + review is our stack).

> **The closing note that outranks the table:** items 1–4 are measured in days and the engine is production-grade. The scarce feature is not code — it is **the launch**. Deploy, post the first "scam of the week," and let real users re-rank this list.
