# Avvalo — v1 Build Scope (one engine, two faces) for the IT Park grant demo

> **ARCHIVED — IMPLEMENTED LEGACY SCOPE, NOT THE CURRENT PRODUCT PLAN.** Current direction:
> [PRODUCT_GUIDE.md](../PRODUCT_GUIDE.md). Current work: [ROADMAP.md](../ROADMAP.md).

> **Status:** Build scope (pre-implementation) · 2026-06-24
> **Goal of this build:** A working demo that wins an **IT Park Uzbekistan** residency/grant — i.e. a credible *platform*, not a single bot.
> **Decision context:** Founder chose **"build the shared engine, demo both faces"** (Avvalo + Avvalo Merchants), targeting **IT Park / grants**. See the strategic discussion that led here and the critique in `V1_MVP_PRODUCT_REVIEW.md`*(removed from repo — see git history)*.
> **Authority:** Vision & safety rules from [PRODUCT_GUIDE.md](../PRODUCT_GUIDE.md) still win on any conflict. Engine details reuse [FAMILY_VALIDATION.md](../FAMILY_VALIDATION.md).
> **Companion:** The executable architecture is [V1_TECHNICAL_PLAN.md](../V1_TECHNICAL_PLAN.md).

---

## 1. What we are building and why this shape

**One backend engine. Two "faces" over it. Two channels (Telegram bot + web app).**

- **Avvalo (free/consumer face):** forward a suspicious message → get a 🚩/✅/❓ read. Reach + mission.
- **Avvalo Merchants (paid/merchant face):** forward a payment screenshot or order chat → get a verification checklist. The revenue *thesis* (path to who-pays).

Both faces are delivered over **two channels**: a **Telegram bot** and a **web app**. The check logic is identical across channels — both call the same engine; the web app just adds anonymous access and the anti-spam controls Telegram gives for free. A clickable web URL also makes the product more demonstrable to a grant panel.

**Why this shape for IT Park:** a single free bot reads as a feature; a **localized UZ/RU AI safety engine that powers two distinct markets** reads as a platform with IT-export and scale potential — the thing grant programs reward. The engine is the asset; the two faces are proof it generalizes.

**The non-negotiable discipline:**

> Build the **engine to production quality once.** Build **Avvalo as the polished demo.** Build **Avvalo Merchants as a thin second skin** — enough to demo the same engine on a merchant problem, *not* a real merchant business (no subscriptions, no team accounts, no payment-provider integration in this build).

The failure mode of "two faces" is building two half-products. The table in §3 exists to prevent that: ~80% of the work is shared, the second face is a rule pack + an output template.

---

## 2. Scope (in / out)

### In scope
- One Telegram bot, **two entry modes** selectable at start (or two separate bots sharing one backend — see technical plan): the *Avvalo* (family/consumer) face and the *Avvalo Merchants* face.
- **A web app** (FastAPI + server-rendered HTMX UI) exposing the same check over the **same engine** — anonymous (no accounts in v1), with Cloudflare Turnstile + rate-limit on image upload. Avvalo is the primary web experience; the endpoint is face-parameterized so Avvalo Merchants works too. Bot and web share 100% of the analysis.
- Inputs: forwarded text, pasted text, one image (screenshot/photo with readable text), optional caption.
- Languages: **Uzbek Latin, Uzbek Cyrillic, Russian** — detect and reply in kind.
- **OCR via cloud provider with a DPA + zero-retention config** for the demo (reviewed decision — see §4). Architecture keeps OCR pluggable so on-prem is a later swap.
- **PII minimization before any LLM call**, preserving *signal structure* (not just stripping) — see §4.
- **Pluggable rule layer**: one rule pack per face (Avvalo = 5 consumer scam families; Avvalo Merchants = ~5 merchant families).
- **LLM explanation** constrained to the fixed output contract + a **specified safety validator**.
- Fixed output: 🚩 red flags · manipulation pattern · ✅ verify · ❓ ask · limitation line. Never a verdict.
- Consent + privacy notice, `/privacy`, `/delete_my_data`, hard content TTLs, privacy-safe analytics, cost/latency instrumentation.
- Per-user daily check limit.
- A short **metrics/admin export** (query or protected endpoint) — enough to show numbers in the pitch.

### Out of scope (this build)
- Accusation graph, entity/person lookup, "reported N×", clusters, public pages. *(Permanently retired — [PRODUCT_GUIDE.md](../PRODUCT_GUIDE.md) §14.)*
- Family groups / shared accounts / guardian-dependent linking.
- Subscriptions, paywalls, team accounts, payment-provider/marketplace integration.
- Mobile app, browser extension. (A **web app is now in scope** — see above; web **accounts/login** are not — web is anonymous in v1.)
- URL browsing, malware scanning, reverse-image search, external reputation lookup, payment confirmation.
- Long-term storage of any submitted content, OCR text, or model output.
- A full admin dashboard UI (a protected export/query suffices).

---

## 3. The leverage: shared engine vs. per-face delta

This is the whole case for "both faces is not 2× the work."

| Layer | Build once (shared asset) | Avvalo face | Avvalo Merchants face (the only delta) |
|---|---|---|---|
| Telegram intake (forward / paste / image) | ✅ shared | reuse | reuse |
| OCR (UZ-Latn / UZ-Cyrl / RU) | ✅ shared | reuse | reuse |
| PII minimization (signal-preserving) | ✅ shared | reuse | reuse |
| **Rule engine (config-driven)** | ✅ shared framework | 5 consumer scam families | **~5 merchant families** |
| LLM prompt + JSON output | ✅ shared | consumer template + system prompt | **merchant template** |
| Safety validator | ✅ shared | reuse | reuse |
| Consent / retention / deletion | ✅ shared | reuse | reuse |
| Analytics / cost instrumentation | ✅ shared | reuse | reuse |

**Net-new for Avvalo Merchants:** ~5 rule families (receipt internal-consistency, order-vs-claimed-amount mismatch, edited-screenshot hints, fake-courier/refund chat patterns, "verify in your real bank app"), one merchant output template, and merchant entry copy. Nothing structural.

**Net-new for the web channel:** a thin FastAPI app + a few Jinja2/HTMX templates + the abuse layer (captcha, IP rate-limit, upload cap) + an anonymous session key. **Zero** engine or analysis code — it calls the same `run_check()`. This is exactly what the "one backend, many thin faces" design buys you.

**Hard rule carried from the guide:** Avvalo Merchants must **never claim money "arrived"** from a screenshot. The merchant face demos the *verification checklist* ("here's what to confirm in your bank app"), not payment confirmation. The payment-provider API that would confirm receipt is the **post-grant moat** — say so in the pitch; it's a strength.

---

## 4. Decisions carried from the v1 review (baked in)

These reverse or pin choices from the original validation spec, per `V1_MVP_PRODUCT_REVIEW.md`*(removed from repo — see git history)*:

1. **OCR = cloud (with DPA + zero-retention) for this build.** The legal driver for on-prem OCR was relaxed on 27 Mar 2026; betting the demo timeline on hard local UZ/Cyrillic OCR is the wrong trade. Keep OCR behind an interface so on-prem is a later swap. Pitch line: *"production roadmap moves OCR on-prem for data-residency."*
2. **PII minimization must preserve signal structure.** Strip the *value*, keep the *signal* as a rule-layer token (e.g. `[LINK: lookalike-domain]`, `[PHONE: claimed-new-number]`, `[CARD: personal-account]`). The rule engine sees raw text locally (pre-minimization) and emits these tokens, so privacy and analysis depth stop fighting.
3. **The safety validator is specified, not asserted.** Deterministic checks for verdict-words, hallucinated contacts (any phone/URL/credential in the output not present in grounded rule signals), and unsafe instructions; defined fail-action (one retry → generic fallback). See the technical plan.
4. **The "no warning signs" path is a first-class, measured output.** Non-reassuring template + tracked fire-rate.
5. **Pin the model: Qwen (open weights) via a neutral OpenAI-compatible host** (OpenRouter / Together / Fireworks). It's the Chinese model with the broadest multilingual coverage (best odds on Uzbek), but served **off mainland China** so user data never enters China — which matters for a privacy/trust product. Provider-abstracted, so the host is one env change. Confirm Uzbek quality with `tools/eval_models.py` before locking. **Self-hosting Qwen in-region is the production roadmap** (full data residency, strongest IT Park line). Cost ceiling ≈ **$0.03/check** holds easily at these token sizes.

---

## 5. What the IT Park pitch needs around the product

Product is necessary but not sufficient. Run these in parallel with the build:

- **Register an entity (MChJ/LLC).** Required for IT Park residency *and* as the legal operator-of-record. One action, two boxes.
- **A small but real number.** A 30–60 person Avvalo mini-alpha + a handful of merchants saying "I'd use this" beats zero. For IT Park these are supporting evidence, not a gate.
- **The platform framing.** Lead the demo with "the engine," show both faces as proof it generalizes; name the roadmap (on-prem OCR, **in-country self-hosted model**, payment-provider API, more faces: JobPass / Fine Print). The model story is a strength: *"open-weight model on neutral infrastructure today, self-hosted in Uzbekistan on the roadmap — your data never goes to a foreign consumer cloud."*
- **A founder-de-risk gesture.** One advisor with fintech / anti-fraud / local-startup credibility.
- **Legal lite.** First-run consent + privacy notice reviewed by a local lawyer before recruiting beyond supervised testers.
- *Verify current IT Park terms/programs* before pitching — the CA scene moves fast.

---

## 6. Success definition for this build

The build is demo-ready when:

- A new user can pick a face, consent, and complete a first check **without instructions**.
- Both faces run on the **same engine** (same intake → OCR → minimize → rules → LLM → validate → format path); the only difference is the rule pack + output template.
- **Both channels (Telegram bot + web app) call the same engine** and return matching output; the web app is anonymous with captcha + rate-limit on image upload, and persists no submitted content.
- All three language forms work for text and image input.
- The 5 Avvalo golden examples ([FAMILY_VALIDATION.md](../FAMILY_VALIDATION.md) §7) pass as fixtures; ≥3 Avvalo Merchants golden examples (authored in the technical plan) pass.
- Safety validator blocks every prohibited output in the test set; no submitted content ever reaches logs/backups.
- p90 latency ≤ 30s text / ≤ 45s image; blended cost ≤ $0.03/check.
- A protected metrics export returns the privacy-safe event counts for the pitch.

---

*Next: the executable architecture and build sequence — [V1_TECHNICAL_PLAN.md](../V1_TECHNICAL_PLAN.md).*
