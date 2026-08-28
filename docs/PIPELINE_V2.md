# Avvalo — Grounded Answer Contract (Pipeline v2)

> **Status:** Active specification
> **Last updated:** 2026-08-28
> **Product authority:** [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md)
> **Supersedes nothing.** This tightens §4 (Output), §5 (Rules) and §6 (Knowledge and model
> boundary) of [V1_TECHNICAL_PLAN.md](V1_TECHNICAL_PLAN.md). The pipeline stages, the statuses,
> the privacy invariants, and the no-verdict rule are unchanged.

## 1. The problem this fixes

Avvalo's detection assets are good and its safety chassis is sound. The answers are weak anyway,
for one structural reason:

**Reviewed content reaches the user only as a suggestion to a language model.**

`knowledge/cards/cards.yaml` holds reviewer-approved `red_flags`, `verify_steps`, and `questions`.
`_render_knowledge()` serializes them into the prompt under the label *"Treat this as reviewed
guidance"*, and the model then paraphrases them into whatever wording it likes. The curated text is
never what the user reads.

The validator cannot catch the drift, because **every check in `_first_rejection_reason()` is
negative**: banned verdict words, leaked contacts, links, card numbers, OTPs, risk scores,
unsupported external-lookup claims, wrong script, empty blocks, list caps, and
`addressed_rule_ids ⊆ known_rule_ids`. Not one check asks whether the *text* has anything to do
with the evidence that was detected.

So this draft passes validation cleanly:

```json
{ "red_flags": ["Ehtiyot bo'ling, noma'lum xabarlarga javob bermang."],
  "verify":    ["Har doim rasmiy manbalarni tekshiring."],
  "ask":       ["Bu xabar haqiqiymi?"],
  "addressed_rule_ids": ["fs.credential.otp"] }
```

Every constraint satisfied. Zero information. The rule pack detected a specific OTP-theft attempt
and the user was told to "be careful online". That is the failure mode this document removes.

A second, smaller source of noise: the rule layer is a flat case-insensitive substring match
(`_rule_matches()`), with no way to express an exception, no word-boundary control for an
agglutinative language, and no co-occurrence logic. Every hit is independent and binary, so a
single ambiguous keyword produces the same authoritative "FACT ALREADY DETECTED" as a decisive one.

## 2. The principle

Today: **the model writes, the validator rejects.**
From here: **the deterministic layer composes, the model localizes, the validator verifies
provenance.**

Concretely — a claim about the user's situation may only reach the user if it can name the detected
evidence it rests on. Advice may be generic; **accusations may not**.

This moves work from the model to reviewed data. It does not add a verdict, a score, or a
person-level conclusion, and it does not weaken any existing check.

## 3. Provenance on red flags (§1)

### Contract

`DraftOutput.red_flags` changes from `list[str]` to `list[Evidence]`:

```python
class Evidence(BaseModel):
    text: str
    source_id: str   # a detected rule_id, a signal kind, or a selected card id
```

`source_id` must be a member of the **evidence set** for this check:

```
known_rule_ids  ∪  {signal.kind for signal in signals}  ∪  selected_card_ids
```

Membership is a set lookup. No model, no similarity scoring, no heuristic — the check is fully
deterministic and costs nothing.

### Failure handling: drop the bullet, keep the answer

An ungrounded bullet is **removed from the draft**, not escalated to a draft-level rejection.
Rejection costs a corrective retry and frequently lands on `safety_fallback`, which replaces a
partly-good answer with fixed copy. Dropping is strictly better: the grounded bullets survive.

The draft is rejected only if dropping leaves it non-compliant — that is, when a severity ≥ 2 rule
hit requires a red flag and none survived. That path already exists
(`REQUIRED_RED_FLAGS_EMPTY`).

`ValidationReason.UNGROUNDED_RED_FLAG` is recorded whenever a bullet is dropped, so the rate is
visible in observability without logging the bullet text.

### Why `verify` and `ask` keep no provenance

They stay `list[str]`, deliberately. In the `no_signal` case there are no rule hits, no signals, and
often no cards — the evidence set is empty, and requiring a `source_id` would make every
`verify`/`ask` bullet ungrounded, emptying both blocks and forcing `VERIFY_BLOCK_EMPTY` on exactly
the path that must still return something useful. Generic verification advice is *acceptable*;
a generic accusation is not. Their quality is governed by §5 (filler blocklist) and §4 (card
composition) instead.

### The compatibility floor

One case is treated differently, because collapsing it would be worse than the problem it solves.

If **no** bullet in a draft carries a `source_id` at all, the model has not implemented the field —
a different failure from citing a bogus ID. Enforcing strictly there would empty every red-flag
block against a provider whose JSON-schema support does not extend to nested objects, turning good
answers into `safety_fallback` copy across the board. So in that single case the bullets are kept
and `grounding_unsupported` is recorded (`log_error(stage="validate",
error_type="GroundingUnsupported")`), making the gap visible instead of silently degrading answers.

As soon as **one** bullet cites an ID, the model has demonstrated it understands the field, and
enforcement is strict for the whole draft: an uncited bullet is then an omission, not a
capability gap.

This matters because the answer model is a third-party host reached over an OpenAI-compatible API,
and `main` deploys straight to production. The floor is what makes the change safe to ship before
that host's nested-schema behavior has been observed in production.

### Prompt and schema

The allowed source IDs are already in front of the model: rule hits render as
`- <rule_id> | family=… | severity=…`, cards render as `- CARD <card.id> version=…`. The JSON schema
gains the nested `Evidence` object with a description naming the three legal ID sources, and
`prompts/check.txt` states the requirement in the output-format section.

### Rollback

Behind `ANSWER_GROUNDING_ENABLED` (default `true`), matching the existing
`URL_REPUTATION_ENABLED` / `KNOWLEDGE_ROUTER_ENABLED` convention. Disabling it restores string
red flags and skips the grounding check. This exists because the change alters the JSON contract
with a live third-party provider, and `main` deploys straight to production.

## 4. Deterministic card composition (§2)

Card text is currently **English-only** — which is precisely *why* it has to be "guidance": the
model is doing the translation. Cards gain an optional localized block:

```yaml
- id: family.credential_theft
  localized:
    uz_latn:
      red_flags: ["Bir martalik SMS kod so'ralmoqda. Bank xodimi buni hech qachon so'ramaydi."]
      verify_steps: ["Suhbatni to'xtating va bank ilovasini o'zingiz oching."]
      questions: ["Bu ma'lumot nega rasmiy ilovadan tashqarida kerak?"]
    ru:
      red_flags: ["Просят одноразовый код из СМС. Сотрудник банка никогда его не спрашивает."]
      verify_steps: ["Прекратите разговор и откройте приложение банка самостоятельно."]
      questions: ["Зачем эти данные нужны вне официального приложения?"]
```

When a **mandatory** card (one selected by `trigger_rule_ids` / `trigger_signal_kinds`
intersection, not by alias cue or router) has a localized block for the resolved reply language, its
bullets are emitted **verbatim**. No model involvement, no paraphrase.

The model's remaining job shrinks to what only it can do:

- `situation_type` triage;
- one `pattern` sentence tying the card to *this* message;
- at most one red flag not already covered by a composed card.

Composed bullets are grounded by construction (`source_id` = the card id) and still pass the full
existing validator, so a bad card cannot bypass the safety chassis.

**Cards without a localized block fall back to today's behavior** — the model localizes them. This
keeps the change additive: the schema and the composition path ship now, and each card becomes
deterministic as its translation is reviewed. Per ROADMAP Phase 2, card text in `uz_latn` / `ru`
is founder/native-reviewer work; an engineer inventing it and stamping `status: approved` would
defeat the review contract.

## 5. Filler blocklist (§3)

`prompts/check.txt` already *asks* for no "be vigilant" / "exercise caution" / broad cyber-safety
lecture. Nothing enforces it. It becomes a deterministic pattern family beside `_UNSAFE_PATTERNS`,
covering `ru`, `uz_latn`, and Cyrillic-Uzbek, and applied per bullet:

- a matching **red flag** is dropped (§3 handling);
- a matching **verify/ask** bullet is dropped if others survive, and kept if it is the last one —
  vague advice beats an empty block and a `safety_fallback`.

Scoped to whole-bullet filler only. A bullet that contains a concrete instruction *and* a stock
phrase is kept: the goal is removing content-free bullets, not policing style.

## 6. Rule-layer precision (§4)

Three additions to `RuleDefinition`, all optional and all backward compatible with every rule and
every `rule_override` row in production today.

### `exclude`

Same per-script shape as `match`. If any exclude pattern matches, the rule does not fire, whatever
else matched. This is the highest precision-per-hour item in this document — it lets a reviewer kill
a specific false positive without weakening the keyword that catches the true ones.

### `match_mode: substring | word_prefix`

Default `substring` (today's behavior, unchanged). `word_prefix` anchors the pattern to a word
start (`(?<!\w)` + the literal), which is what Uzbek agglutination needs: `kod` then matches
`kodni`, `kodingizni`, `kodini` without enumerating them, while `bikod` no longer matches. It still
matches `kodeks` — that is what `exclude` is for; the two are designed to compose.

The existing `regex:` pattern prefix is unaffected and remains the escape hatch for anything
neither mode expresses.

### `requires`

A co-occurrence gate evaluated in a second pass, after base matching:

```yaml
requires:
  any_of: [fs.urgency.deadline, fs.authority.bank]   # at least one must have fired
  all_of: []                                          # every one must have fired
  signals: [card]                                     # signal kinds that must be present
```

This is what lets a broad, high-recall keyword exist without firing on its own: "prepayment" alone
is ordinary commerce; "prepayment" plus urgency plus a personal card transfer is not.

**Load-time constraint:** a rule carrying `requires` may only reference rules that do *not*
themselves carry `requires`. This keeps evaluation to a single deterministic pass with no
fixpoint iteration and no ordering dependence, and it is validated when the pack loads — a
violation fails the pack, which falls back to the shipped YAML baseline exactly like any other
load failure.

## 7. Measurement (§5)

None of §6 is tunable without numbers. `tools/eval_rules.py` runs the rule layer over a labeled
corpus and reports per-rule precision, recall, and the false-positive rate on benign input:

```
tests/fixtures/eval/corpus.json
  { "id": …, "text": …, "language": …, "expected_rule_ids": [...], "benign": bool }
```

It exits non-zero when the benign false-positive rate exceeds its threshold, so a keyword change
that boosts recall by carpet-bombing ordinary messages fails visibly instead of shipping.

**The benign half is the half that matters** and the half that does not exist today: 13 golden
fixtures are a smoke test for the answer format, not a precision metric for detection. The corpus
ships seeded with ordinary Uzbek and Russian messages (deliveries, marketplace haggling, family
chatter, real bank notifications) — the traffic that must *not* trip a rule.

Real scam material for the positive half stays ROADMAP Phase 2 founder work, sourced from actually
circulating messages. It is never sourced from user submissions: those are ephemeral by design.

## 8. What does not change

Stated explicitly, because this touches the validator and the model boundary:

- **No verdict, no score, no person-level conclusion.** Grounding decides whether a bullet may be
  *shown*, never whether a situation is "safe" or "scam". The only status decision remains
  `no_signal` vs `ok`.
- **Every existing validator check stays.** §3 and §5 add checks; nothing is relaxed.
- **Privacy invariants hold.** `source_id` values are rule/signal/card identifiers — already
  persisted in `check_event.rule_ids` and `knowledge_card_ids`. No bullet text is logged or
  persisted, including dropped bullets; the observability trail carries counts and reasons only.
- **No product discriminator.** Nothing here reintroduces `face`, a "mode", or a product parameter.
- **Statuses are unchanged.** No new `CheckStatus` member; no change to `BILLABLE_STATUSES`.
- **No new runtime dependency.**

## 9. Order of work

| # | Item | Touches | Status |
|---|------|---------|--------|
| 1 | Provenance + grounding check (§3) | `types.py`, `validate.py`, `prompt.py`, `pipeline.py`, `config.py` | **done** |
| 2 | Filler blocklist (§5) | `validate.py` | **done** |
| 3 | Rule-layer precision (§6) | `rules/loader.py`, `rules/engine.py`, `rules_store/`, migration `0012` | **done** |
| 4 | Precision controls in the operator editor | `web/rules_admin.py`, `rules_copy.py`, `admin_rule_form.html` | **done** |
| 5 | Eval harness + benign corpus (§7) | `tools/eval_rules.py`, `tests/fixtures/eval/` | **done** |
| 6 | Card localization + composition (§4) | `knowledge/`, `pipeline.py` | **done (inert)** |
| 7 | Reviewed `uz_latn` / `ru` card text | `knowledge/cards/cards.yaml` | **founder** |
| 8 | Real circulating scam material for the corpus | `tests/fixtures/eval/corpus.json` | **founder** |

Items 1–5 are live on merge. Item 6 ships the machinery but changes no answer until a card carries
a `localized` block, so it is inert until item 7. Items 7 and 8 are content, not code: authoring
card wording or scam intelligence and stamping it `approved` without native review would defeat the
review contract these assets exist to carry.

### Known finding from the first eval run

`fs.secrecy.tell_nobody` fires on a **legitimate bank SMS** in Uzbek — "Ilovaga kirish uchun kod:
7391. *Uni hech kimga aytmang.*" — because a bank telling you to keep your code private matches the
same keyword as a scammer telling you to keep the situation secret. One benign message in twenty,
a 5.0% false-positive rate, entirely from this rule.

The fix is one `exclude` entry, which §6 now supports and item 4 makes reachable from
`/admin/rules`. It is deliberately **not applied here**: narrowing a shipped detection rule changes
what production catches, and which phrasing to carve out is a native-reviewer judgment, not an
engineering one.

## 10. Acceptance

- `pytest -q` green, with new coverage for: an ungrounded bullet dropped, a grounded bullet kept, a
  drop that empties a required red-flag block still rejecting, `exclude` suppressing a hit,
  `word_prefix` matching an inflected form, `requires` gating a rule, and a localized card composing
  verbatim.
- `ruff check .` clean.
- `tools/eval_rules.py` runs and reports a benign false-positive rate.
- Every existing test passes unmodified. A test changed to accommodate new code is a regression in
  the change, not in the test.
