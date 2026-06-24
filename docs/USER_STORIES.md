# Avvalo — User Stories (v1)

> Derived from [PRODUCT_DESIGN.md](PRODUCT_DESIGN.md) Section 16 (function list).
> **Last updated:** 2026-06-20
> Format: *As a [persona], I want [goal], so that [benefit]* + acceptance criteria.
> Tags: `[TG]` Telegram-only in v1 · `[WEB]` web-only · `[ADMIN]` admin dashboard · (untagged = both clients)

## Personas

- **Dilnoza — the worried buyer** (primary v1 user): about to pay or share data with a Telegram/Instagram seller; wants a fast gut-check.
- **Aziz — the victim / reporter**: was scammed (or nearly); wants to warn others and check if an account is already known.
- **Returning user**: came back after a previous check; cares about history and alerts.
- **Sardor — the accused**: believes a claim about his number / handle is wrong and wants it reviewed and removed.
- **You — the moderator / founder**: keeps the graph accurate and the data trustworthy.
- *(Anti-persona)* **Malik — the abuser / scammer**: tries to flood false reports, clear his own record, or spam the bot. Stories must defend against him.

---

## Epic 1 — Check a suspicious situation (core)

**US-1.1 — Guided check**
*As Dilnoza, I want to pick what I'm checking and paste/forward the seller's Telegram or Instagram handle, phone, or screenshots, so that I get specific red flags and what to verify before I pay.*
- Bot shows category buttons (`Payment / Seller / Job offer / Investment / Other`).
- Accepts freeform text **and** image uploads (screenshots, photos).
- Returns the fixed **🚩 red flags / ✅ verify / ❓ ask** block in the user's language.
- If any extracted entity matches the graph, an **⚠️ evidence line** is appended.
- **Never** outputs a score or a "safe/unsafe" verdict.

**US-1.2 — Quick entity lookup**
*As Dilnoza, I want to paste just a Telegram username, Instagram handle, or phone number and instantly learn if it's been reported, so that I get a fast answer without waiting for a full analysis.*
- Returns an instant graph answer: *"reported N× this month"* or *"no known records."*
- Works on the **primary identity entities** (Telegram / Instagram / phone) first.
- **Does not** consume the daily AI-analysis limit (it's a cheap lookup).

**US-1.3 — Story with no lookupable entity**
*As a user describing a phone call with no handle or number, I want the bot to still analyze my story, so that I get useful guidance even when there's nothing in the database to look up.*
- LLM + rule layer run on the text alone; the 🚩/✅/❓ block is still produced.
- Output clearly says *"no known records found"* rather than implying the situation is safe.

---

## Epic 2 — Report a scammer (data loop)

**US-2.1 — Standalone report** `[TG]`
*As Aziz, I want to report a scammer's Telegram/Instagram handle and phone with evidence — without doing a check first — so that I can warn other people.*
- Dedicated **"Report a scam"** command/button.
- Collects the identity entities + optional screenshots + a **scam-pattern tag** (prepayment-then-disappear, fake delivery, job-deposit, etc.).
- Confirms submission; the report is **rate-limited** per user.

**US-2.2 — Post-check report**
*As a user who just checked someone who turned out to be a scammer, I want to confirm "yes, it was a scam" in one tap, so that my experience strengthens the graph for others.*
- A *"Did this turn out to be a scam? [Yes / No / Not sure]"* prompt appears after each check.
- A "Yes" links the report to the entities from that check.

**US-2.3 — Trustworthy evidence (moderation)**
*As Dilnoza reading a result, I want the evidence to be trustworthy, so that I'm not misled by fake or malicious reports.*
- Low-stakes reports surface to others only after **N independent corroborating reports**.
- High-impact reports (a specific named person/business) are held in the **admin review queue** first.
- A single uncorroborated report is **never** shown to others as established fact.
- *(Defends against Malik flooding false reports.)*

**US-2.4 — Two-sided abuse defense** `[ADMIN]`
*As the moderator, I want reports and disputes rate-limited and trust-weighted in both directions, so that a scammer can neither flood false reports against an innocent nor clear his own record by spamming disputes.*
- Reports **and** disputes are rate-limited per user and weighted by **reporter / disputer trust-score**.
- Retaliatory reporting (against a competitor) and self-clearing dispute-spam are throttled; high-impact actions route to admin review.
- *(Defends against Malik in both directions.)*

---

## Epic 3 — Stay protected over time (retention & growth)

**US-3.1 — Watch + notify** `[TG]`
*As a user who checked a seller, I want to be alerted if that seller is later reported by others, so that I find out about danger even after my check is done.*
- When an entity the user checked crosses the report threshold, the bot proactively messages them.
- The message references **what they checked** and the **new evidence** (*"the account you checked last week was just reported 3×"*).

**US-3.2 — Recent-checks history** `[TG]`
*As a returning user, I want to see my recent checks, so that I can revisit an earlier result.*
- `/history` lists the user's recent checks and their results.

**US-3.3 — Share + invite**
*As a user who got a useful result, I want to share it with a friend, so that I warn them and they discover the bot.*
- A **Share** button forwards a clean summary + a bot deep-link.

---

## Epic 4 — Understand scams (education & trust)

**US-4.1 — Contextual education tips**
*As a user checking a job offer, I want a one-tap "how this scam usually works," so that I recognize the pattern next time.*
- Short, category-specific explainers surfaced in context (1 tap, not a wall of text).

---

## Epic 5 — Moderate & operate (admin)

**US-5.1 — Review queue** `[ADMIN]`
*As the moderator, I want to review high-impact reports before they affect others, so that I prevent defamation and report-poisoning.*
- Queue of pending high-impact reports with evidence; approve / reject actions.

**US-5.2 — Entity & cluster management** `[ADMIN]`
*As the moderator, I want to view, correct, and merge entities into a scammer cluster, so that the graph stays accurate and one actor's identifiers stay linked.*
- View entity + linked reports; merge duplicates; link/unlink identifiers into a **scammer-profile cluster**.

**US-5.3 — Rule-library editor** `[ADMIN]`
*As the moderator, I want to add/edit per-category red-flag rules as config, so that I can respond to new scam patterns without a redeploy.*
- Rules editable as data; changes take effect without shipping code.

**US-5.4 — Abuse controls** `[ADMIN]`
*As the moderator, I want to rate-limit and ban abusive reporters, so that the data stays clean.*
- View abuse signals; throttle or ban a user/IP. *(Defends against Malik.)*

**US-5.5 — Metrics dashboard** `[ADMIN]`
*As the founder, I want a dashboard of checks, graph-match rate, report volume, and cost-per-check, so that I can track traction, the moat, and unit economics (for fundraising).*
- Headline metric: **graph-match rate trending over time** (the moat made visible).

---

## Epic 6 — Contest a claim (the accused)

**US-6.1 — Dispute & removal** `[TG]`
*As Sardor, who believes a claim about my number or handle is wrong, I want to contest it and have it reviewed, so that an incorrect accusation is suppressed and removed.*
- A **`/dispute` command** (plus a published contact channel) lets a subject submit the identifier in question + counter-evidence.
- On submission the identifier is marked **`disputed`** and **suppressed as a negative signal while under review.**
- Admin adjudicates (US-5.1) → **`cleared`** (removed as a negative signal; cluster edge cut) or dispute rejected with a logged reason, within a stated SLA.
- Disputes are **rate-limited + trust-weighted** so the flow can't be abused to self-clear.

---

## Cross-cutting / non-functional stories

**US-X.1 — Language**
*As an Uzbek- or Russian-speaking user, I want the bot to reply in my language automatically, so that I understand the result.*
- Auto-detect input language; reply in the same (UZ / RU).

**US-X.2 — Soft-degrade over the limit**
*As a heavy user who has used today's AI checks, I want to still get the free graph lookup, so that I always get something useful.*
- Over the AI limit → the cheap graph lookup still runs; a clear message explains the limit.

**US-X.3 — Privacy of sensitive data**
*As a user, I want my sensitive data (card numbers) to never be stored in full, so that I can trust the service.*
- Cards stored as **BIN + last4 + hash only**, never the full PAN; data stored on UZ servers (data-localization).

**US-X.4 — First-run consent**
*As a new user, I want to see what data is stored and why before I use the bot, so that I can give informed consent.*
- On first `/start`, a one-time **consent / privacy notice** (what's stored, why, retention, how to dispute) is shown; **consent version + timestamp are recorded** before any processing.

**US-X.5 — No data leakage via lookup**
*As someone whose number was reported, I want lookups to reveal only aggregate evidence, so that my report and identity aren't exposed and the DB can't be mined.*
- Quick-lookup returns **aggregate evidence only** (*"reported N×"*) — never report text or reporter identity.
- Quick-lookup is **rate-limited** per user / IP to prevent enumeration of the database.
