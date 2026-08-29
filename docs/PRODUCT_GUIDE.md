# Avvalo — Product Guide

> **Status:** Canonical product direction
> **Last updated:** 2026-08-28
> **Rule:** If another document conflicts with this guide on product scope, this guide wins.

## 1. Product in one sentence

Avvalo helps people in Uzbekistan check a suspicious link, QR code, message, or situation
before they pay, reply, install, sign, or share personal information — and tells them what
to do when it has already happened.

> **Verify the situation, artifact, or process — never the reputation of a person.**

The promise, in the form the user reads it:

> **Avvalo does not tell you something is safe. Avvalo makes you hard to deceive.**

That sentence is the product. The refusal to issue verdicts is not a limitation worked
around — it is the positioning, and it is the one property a competitor built as a wrapper
around a language model does not have and cannot retrofit.

## 2. What changed, and why this document was rewritten

Avvalo was previously scoped as an incident helper: a person arrives frightened, submits one
situation, reads one answer, leaves. That framing is now retired. The unit of value is no
longer a resolved case but the user's own acquired ability to notice what is wrong.

Concretely, three things changed:

1. **One reactive flow became three capabilities** — Scanner, Check, Knowledge (§4).
2. **The answer became decisive** — about the action, never about the object (§5).
3. **The product became an application inside Telegram**, not only a bot and a web form (§6).

Removed from scope in the same pass, deliberately and not by omission: the digital-hygiene
checklist, the phishing trainer, the personal counter, voice answers, an answer variant
addressed to a third party, result-as-image export, Telegram account verification, and a
second on-device implementation of the URL analyzer. §9 holds the full list.

## 3. Audience

Deliberately broad: any person in Uzbekistan whose daily life runs through Telegram, Click
and Payme, OLX and Uzum, bank SMS, and QR payments. The product is not narrowed to a
segment.

Reply languages are `uz_latn` and `ru`. Cyrillic-Uzbek input is detected and understood
today but is always answered in `uz_latn`; adding Cyrillic-Uzbek **output** is scheduled
work (ROADMAP Phase 3) because the group most exposed to fraud reads Cyrillic fluently and
Latin with difficulty. Until that ships, the audience is not broad — it is truncated by age.

## 4. What the product does

Three capabilities, one engine behind all of them.

### Scanner

A pasted link or a QR code, answered immediately from deterministic analysis with no model
call. Resolving where a shortened link leads is part of this, inside the boundaries in §8.1.
This is what a person reaches for while paying by QR or after receiving a link in a chat.

### Check

The full situation analysis in chat: a message, a screenshot, a forwarded conversation, an
offer, a payment request. It also covers the "it already happened" situations — money
already transferred, a code already received, an account already stolen, a call in progress,
a deal about to close. Those are inputs to the same chat, never separate screens.

### Knowledge

Founder-written explanations of real schemes, a rare notification about a circulating wave,
and a forwardable one-screen reminder. This is what a person reads when they recognise their
own story in someone else's.

**Limits differ because costs differ.** The Scanner performs no model call, so it is
generous and bounded only by abuse protection. The Check costs a model call and stays under
`DAILY_CHECK_LIMIT` (default 5). The Scanner is the funnel into the Check: one button,
"need a full analysis?".

## 5. The answer contract

### 5.1 The core decision: decisive about the action, not about the object

A user wants to know whether they can tap. The product may not say "safe". Both are
satisfied by moving the decisiveness: **a verdict describes the object; a recommendation
describes the action.**

"This site is fraudulent" is unprovable and legally exposed. "Do not enter your card here —
open your bank's app yourself" is always correct, concrete, and actionable.

The screen may look categorical — a large state, colour. What is categorical is the
recommended action, never a claim about the site.

### 5.2 Scanner answer (short form)

Three states, all decisive:

| Finding | What the user sees |
|---|---|
| A specific signal | Name the signal in plain language → **the safe action to take instead** |
| Nothing found | "Nothing suspicious in this address" → **this does not mean the site is genuine**; what to check |
| Could not parse | "Could not read this address" → **what to do instead** |

The "nothing found" state must never be phrased as an absence of risk. It reports the
absence of a *finding*, which is a different statement.

### 5.3 Check answer (long form)

Unchanged from the existing implementation, in this order:

1. **What deserves attention** — red flags grounded in a detected rule, signal, or card.
2. **What to do now** — concrete independent action.
3. **What remains unknown** — limits of what was checked.
4. **What to ask** — short questions for the counterparty or the organisation.

A red flag that cannot name the rule, signal, or card it rests on is dropped rather than
shown (`ANSWER_GROUNDING_ENABLED`, default on).

Both forms pass through the same deterministic validator
([app/engine/validate.py](../app/engine/validate.py)), which bans verdict words in `ru`,
`uz_latn`, Cyrillic-Uzbek and English, strips contacts, links, card numbers and OTPs, and
caps list lengths. One corrective retry, then `safety_fallback`.

## 6. Product surfaces

| Surface | Carries | State |
|---|---|---|
| **Telegram Mini App** | Three tabs: Scanner · Check · Knowledge. QR capture uses Telegram's built-in scanner; we do not write our own camera | To build |
| **Telegram bot** | Conversational entry: send a screenshot, get an analysis. Later, family-group use and in-conversation checks | Built |
| **Web** | Anonymous entry without Telegram, plus the published Knowledge pages | Built |

Free-form input stays the default and largest door on every surface. Specialised entries are
shortcuts for a person who already knows what they are holding — never a fork every user
must pass through. **An entry point configures the input field; it never changes the engine
or the shape of the answer.** There is no product discriminator on `CheckInput`; the absence
of `face` is asserted by `tests/test_types_contract.py`.

## 7. What is built today

Verified against the repository, not assumed:

- Telegram bot and anonymous web intake; `/privacy` and `/delete_my_data`.
- OCR (`OCR_PROVIDER`, default `rapidocr`) with a confidence gate, and local in-process QR
  decoding via `zxing-cpp` ([app/engine/qr/](../app/engine/qr/)).
- One URL analyzer ([app/engine/url.py](../app/engine/url.py)) shared by rule matching,
  minimization and reputation lookup, producing six shape labels: `shortened`,
  `lookalike-domain`, `domain-in-subdomain`, `mixed-script-domain`, `credentials-in-url`,
  `ip-address`.
- The full check pipeline ([app/engine/pipeline.py](../app/engine/pipeline.py)) with rate
  limiting, language resolution, deterministic rules, PII minimization, an LLM call in
  JSON-schema mode, the safety validator, and localized formatting.
- Database-backed rule and card overrides with founder editors at `/admin/rules` and
  `/admin/cards`, each with a dry run against the real matcher.
- A founder-authored Knowledge section (`/cases`) with draft/publish administration.
- Retention, deletion auditing, pseudonymous user keys, privacy-safe events.

**Detection assets are thin.** The shipped baseline is 13 rules, 10 knowledge cards, 14
organizations in the official-domain catalog, and 13 golden end-to-end cases. All of the
rules and cards describe *universal* patterns — OTP requests, urgency, prepayment. None is
specific to Uzbekistan. `rules/shared/uz_phishing_domains.yaml` contains zero domains and
`URL_REPUTATION_ENABLED` is off, so the reputation store currently changes no answer.

This baseline can explain what is suspicious. It cannot yet explain a local scheme better
than a general-purpose assistant can, and no product surface compensates for that.

**Not built:** the Mini App, the short scanner answer, redirect resolution, Cyrillic-Uzbek
output, wave notifications (there is no broadcast infrastructure of any kind today),
first-run examples, the forwardable reminder, family-group behaviour, and inline mode.

## 8. Privacy and safety invariants

These carry the legal posture and are enforced by tests that fail the build.

- **Submitted content is never persisted or logged.** `raw_text`, `image_bytes` and
  `caption` on `CheckInput` are ephemeral. `check_event` rows and `log_event()` output carry
  only IDs, enums, rule IDs, and metrics.
- **No table has a content column.** `tests/test_schema_privacy.py` rejects content-like
  persistence against an empty allowlist. The last text column, the retired flow's
  `story_submission.minimized_text`, was dropped in migration `0013`.
- **Users are pseudonymous.** `user_key = HMAC_SHA256(APP_HMAC_SECRET, telegram_id)[:32]`;
  raw Telegram IDs are never stored or logged.
- **No verdicts.** The product never outputs "safe", "scammer", "fraud confirmed", a trust
  score, or a risk score, in any supported language.
- **Situation, not person.** No dossier on a person, phone number, card, account, or handle
  — not now and not as an extension.
- **We do not open submitted pages.** No code path fetches, renders, or executes a submitted
  destination.

### 8.1 The one bounded exception: redirect resolution

Resolving where a shortened link leads is a product feature (§4, Scanner). It is a
deliberate, narrow exception to the rule above, and its boundaries are part of the spec:

- **`HEAD` only.** No response body is downloaded, no page is rendered, no script executes.
- **`https` only, public addresses only.** Private, loopback, and link-local ranges are
  refused before the request is made. This is what closes SSRF.
- **Bounded.** Hard timeout, at most five redirect hops, no cookies, no credentials.
- **Explicit.** Runs only on a user's deliberate tap ("show where this leads"), only for
  hosts the analyzer classified as shorteners — never automatically on every submitted URL.
- **Egress is separated** from the application's primary address.
- The resolved destination is shown to the user and then discarded. It is not persisted, not
  logged, and not sent to a model.

Anything beyond this — fetching page content, rendering, screenshots, sandboxed browsing —
is out of scope and requires a new founder decision recorded in this file. The exception
must not widen by drift.

## 9. Non-goals

Cut deliberately during scope planning, not forgotten. A one-person, evenings-only build
pays for every extra surface with emptiness in the others.

Cut from this plan: digital-hygiene checklist · phishing trainer · personal check counter ·
voice answers · an answer variant written for a third party · result-as-image export ·
Telegram account verification against the catalog · a second on-device URL analyzer · PDF
and voice-message input · a clarifying-dialogue answer mode · an "I'm on a call right now"
screen · rule-attribution display · home-screen install.

Permanently out of scope: Avvalo Merchants or any merchant-first direction · separate
products for jobs, deals, links, documents, or payments · an accusation database, public
allegation pages, or an open forum · user-generated posts, comments, ratings, or an
accusation feed · a searchable person database · person, phone, card, or handle reputation
lookup · screenshot, receipt, document, or deepfake authenticity verdicts · general
autonomous browsing or reverse-image search · training a model on submitted checks ·
payment, escrow, or marketplace infrastructure.

**Avvalo Verify** — verified facts from official registries, specified in
[VERIFY_VALIDATION.md](VERIFY_VALIDATION.md) — is parked, not cancelled. It is not part of
this plan and no implementation task may be written for it. The official-domain catalog it
depends on is being built anyway, as lookalike detection, so parking costs nothing.

## 10. Documentation authority

- This file defines the product and the safety boundary.
- [ROADMAP.md](ROADMAP.md) defines the order of work.
- [V1_TECHNICAL_PLAN.md](V1_TECHNICAL_PLAN.md) describes the implemented architecture.
- [AI_KNOWLEDGE_PIPELINE.md](AI_KNOWLEDGE_PIPELINE.md) defines explanation knowledge; a
  knowledge card is not official-source evidence.
- [VERIFY_VALIDATION.md](VERIFY_VALIDATION.md) is parked; see §9.

Superseded ideas and implementation records belong in Git history, not in the active
documentation tree.
