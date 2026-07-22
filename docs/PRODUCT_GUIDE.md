# Avvalo — Product Guide

> **Status:** Canonical product direction
> **Last updated:** 2026-07-22
> **Rule:** If another document conflicts with this guide on product scope, this guide wins.

## 1. Product in one sentence

Avvalo helps people in Uzbekistan check a suspicious situation before they reply, pay,
install something, sign, or share personal information.

> **Verify the situation, artifact, process, or source — never the reputation of a person.**

Avvalo is one consumer product. Links, QR codes, payment requests, job offers, documents, and
messages are different inputs to the same flow, not separate products.

The habit we want to create is simple:

> **Have doubts? Send it to Avvalo before you act.**

## 2. The complete product loop

> **Send → Understand → Verify → Act → Share**

### Send

The user can submit pasted or forwarded text, a screenshot or photo, a link, a QR code, or a
suspicious payment request, offer, document, or conversation. The channels are Telegram and the
anonymous web checker. The supported reply languages are `uz_latn` and `ru`. Cyrillic-Uzbek
content is still understood and matched, but it is always answered in `uz_latn`.

### Understand

Avvalo explains the details that deserve attention, pressure or manipulation patterns, claims that
need independent confirmation, and questions the user should ask. This is an explanation, not a
verdict about a person or organization.

### Verify

**Avvalo Verify** is the signature capability. It checks only facts that can be established safely
through an approved official source, curated official-contact catalog, or versioned local snapshot.

Each displayed fact states what was established, the named source, when it was observed, and what
it does not prove. A failed check is `unavailable`. An artifact absent from one source is only
`not_found` in that named source; absence is never a conclusion about legitimacy.

### Act

Avvalo gives the safest useful next action: independently open the official site or app, call an
official number, inspect a register, delay payment or data sharing, or ask a trusted relative.

### Share

The user may share a sanitized warning or invite another person to check with Avvalo. Shared output
contains only deterministic, non-identifying metadata and safe advice. It never reproduces submitted
content, contacts, payment details, or an accusation.

Share is distribution support, not a public allegation page, story network, or content community.

## 3. What exists and what comes next

### Built baseline

The repository already contains:

- Telegram and anonymous web intake;
- text and image processing with OCR;
- local rules and signals, PII minimization, and reviewed knowledge retrieval;
- LLM explanation behind a deterministic safety validator;
- localized output in all three language forms;
- consent, deletion, rate limits, privacy-safe events, and retention controls;
- a sanitized sharing foundation;
- local hash-based URL-reputation support that may remain disabled until production verification.

The runtime exposes one active face, internally named `family`. Seller, payment-screenshot,
courier, and refund situations enter this same checker; the relevant payment protections are part
of the main rule and safety path. Avvalo Merchants, the scam library, story capture, and Scam Pulse
are not dormant modes — they are retired surfaces.

This baseline can explain what is suspicious and what the user should verify. It must not be
described as having checked an official source unless a typed Avvalo Verify result exists.

### Next product capability

The next capability is the strict Avvalo Verify MVP in §4. It is **not yet authorized for
implementation**. First it must pass [VERIFY_VALIDATION.md](VERIFY_VALIDATION.md).

## 4. Avvalo Verify MVP

Only three verification families belong to the MVP.

### 4.1 Official identity match

Maintain a founder-reviewed catalog for commonly impersonated organizations: official name,
domains, support pages, published Telegram handles, source URL, and last-reviewed time.

Avvalo may report an exact match or exact mismatch. A match never makes the whole situation safe.

### 4.2 Link and QR evidence

Avvalo may decode a QR code locally, normalize the destination domain including punycode and
deceptive subdomains, compare it with the official catalog, and consult a local cached
URL-reputation dataset.

Avvalo must not open, render, or execute an arbitrary submitted page. Submitted URLs and domains
remain ephemeral and are not echoed back by default.

### 4.3 Regulated organization and license routing

Use only named official sources appropriate to the claim, such as Central Bank registers, official
license search, or another permitted state register.

Prefer scheduled local snapshots. When a source has no permitted API or requires authentication,
provide a sourced official deep link and a safe extracted search value instead of scraping the site
or pretending the check succeeded.

### Outside the MVP

- general autonomous web search or reverse-image search;
- arbitrary announcement search;
- screenshot, receipt, document, or deepfake authenticity verdicts;
- person, phone, card, account, or handle reputation lookup;
- automatic reports or messages to third parties.

## 5. User-visible answer contract

A completed answer contains these blocks, in order:

1. **What Avvalo could establish** — at most three decision-relevant source facts.
2. **What deserves attention** — red flags in the submitted situation.
3. **What to do now** — concrete independent action.
4. **What remains unknown** — limitations and unavailable checks.
5. **What to ask** — short questions for the counterparty or official organization.

Allowed evidence statuses are `supported`, `exact_mismatch`, `not_found`, and `unavailable`.
The answer never aggregates them into a score or verdict.

## 6. Evidence rules

Evidence is structured data, not model prose. Every adapter result contains a stable fact ID,
status, deterministic claim template, source name, source URL, observation time, and limitations.

The LLM may explain allowlisted facts. It may not browse unrestricted sources; invent a fact,
citation, lookup, or timestamp; turn `not_found` into “does not exist”; turn a match into “safe”;
or combine facts into a person-level judgment.

Unknown fact IDs, missing source metadata, stale data outside its freshness window, or an adapter
failure must fail closed and produce `unavailable`.

## 7. Privacy and safety

- Submitted text, OCR text, captions, images, URLs, contacts, and generated answers are ephemeral
  and are not persisted or logged.
- The existing `story_submission.minimized_text` field is a legacy stewardship-only exception.
  No current flow writes or reads it. Existing rows remain covered by `/delete_my_data` and
  retention until a separately authorized data purge; the table must not become a content source.
- Raw screenshots stay inside the controlled OCR boundary; only minimized text may reach an
  external LLM.
- Source snapshots contain public reference data, never user submissions.
- Avvalo never claims to have checked every database.
- Avvalo never outputs “safe,” “scammer,” “fraud confirmed,” a trust score, or a risk score.
- Avvalo never contacts a counterparty or institution for the user.
- Every user-facing string exists in `uz_latn` and `ru`.

## 8. Validation gates

Before implementation, the manual test must show:

- at least 40% of representative scenarios produce a decision-relevant source fact;
- at least 70% of participants prefer the evidence-backed answer to advice alone;
- zero invented, overstated, unsourced, or person-level facts.

After implementation, the measured alpha must show:

- at least 60 activated users and 150 completed real checks;
- evidence coverage of at least 35%;
- audited fact precision of at least 98%, with zero critical false facts;
- at least 70% evidence usefulness and at least 25% decision impact;
- 100% of displayed facts carry source and observation time;
- zero privacy incidents and zero person-level verdicts.

Definitions and the procedure live in [VERIFY_VALIDATION.md](VERIFY_VALIDATION.md).

## 9. Current sequence

1. Finish and record production smoke verification for the built baseline.
2. Produce the 30-scenario Avvalo Verify validation packet.
3. Run paired advice-only versus evidence-backed sessions.
4. Make one explicit `go`, `revise once`, or `stop` decision.
5. Only after `go`, write one executor-ready task for the three-family MVP.
6. Build and audit the narrow MVP.
7. Run the measured alpha before expanding scope.

The executable order is maintained in [ROADMAP.md](ROADMAP.md).

## 10. Non-goals

- Avvalo Merchants or any merchant-first direction;
- separate products for jobs, deals, links, documents, or payments;
- an accusation database, public allegation pages, or an open forum;
- a content library, story flywheel, trend feed, or training product as the current strategy;
- voice, group monitoring, family accounts, a mobile app, or new product faces;
- general-purpose browsing or an agent that “checks everything”;
- collecting submitted content so a model can learn;
- payment, escrow, or marketplace infrastructure;
- choosing a revenue model before the core evidence behavior is validated.

## 11. Documentation authority

- This file defines the product and safety boundary.
- [ROADMAP.md](ROADMAP.md) defines the order of work.
- [VERIFY_VALIDATION.md](VERIFY_VALIDATION.md) defines the experiment.
- [V1_TECHNICAL_PLAN.md](V1_TECHNICAL_PLAN.md) defines the current implemented architecture.
- [AI_KNOWLEDGE_PIPELINE.md](AI_KNOWLEDGE_PIPELINE.md) defines explanation knowledge; a knowledge
  card is not official-source evidence.

Superseded ideas and implementation records belong in Git history, not the active documentation
tree.

Any new feature stays outside the active roadmap until evidence shows it is more important than
improving this core loop.
