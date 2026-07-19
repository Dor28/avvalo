# Avvalo — Improvement Backlog (executor-ready task prompts)

> **Status:** T-01–T-07 implemented and re-verified on `codex/improvement-backlog` · 2026-07-19. Founder-only launch activities at the end remain open.
> **Authority:** [PRODUCT_GUIDE.md](PRODUCT_GUIDE.md) wins on safety and scope. [ROADMAP.md](ROADMAP.md) remains the phase plan; this file does not replace it — it holds the *executable prompts* for the engine work the roadmap calls for, in the order they should be done.
> **Audience:** an implementing model or engineer with repository access, one task per session.

## How to use this file

Each task below is a self-contained prompt. Copy the fenced block into a fresh session, let it finish, review, then move to the next. **Do not run two tasks in one session** — they share files and the review gets muddy.

Every task assumes: branch `launch-features`, never push to `main` (that deploys to production), `pytest -q` and `ruff check .` must be green at the end, and no submitted content may ever be persisted or logged.

## Priority and reasoning

The ordering is not by size — it is by what unblocks what.

| # | Task | Why here | Rough size |
|---|---|---|---|
| **T-01** | Knowledge layer: prod fix + test suite | The layer is currently dead in the container and unverified everywhere. Nothing below is trustworthy until this lands | 1 day |
| **T-02** | Correct the stale audit table | The contract doc claims six implemented things are missing. A false map is worse than no map | 1 hour |
| **T-03** | Knowledge-gap report | This is the system's sense organ. Without it, "improving the cards" is guesswork | 0.5 day |
| **T-04** | Coverage + time-to-card metrics | Turns improvement from a feeling into two numbers | 0.5 day |
| **T-05** | Semantic router | Fixes the inflection recall gap that substring aliases cannot fix | 1–2 days |
| **T-06** | Validator: per-fact rule preservation | Named as weak in the project's own audit and never fixed. Safety-critical | 1 day |
| **T-07** | URL reputation stage (R6) | Cheapest real detection lift per [ML_RESEARCH.md](ML_RESEARCH.md) §4; already scoped | 2–3 days |

Execution result: all seven engineering prompts are complete in the current branch. The final
acceptance run is recorded in [AI_KNOWLEDGE_PIPELINE.md](AI_KNOWLEDGE_PIPELINE.md) §8; R0 and
R6 branch status is recorded in [ROADMAP.md](ROADMAP.md). This does not claim that the
founder-only production smoke, weekly card review, or user-distribution work has happened.

**Read this before planning past T-04.** T-01 through T-04 make the system *measurably* improvable. T-05 through T-07 make it *better*. Neither group creates the compounding asset — that requires real submissions, and the project has zero users. Everything in this file is worth roughly two weeks of engineering; if it takes longer than that, the work has drifted from the actual bottleneck, which is distribution.

---

## T-01 — Knowledge layer: production fix + acceptance suite

```
You are working in the Avvalo repository (Python 3.11, async, pytest). Read CLAUDE.md first;
its rules override your defaults. Branch: launch-features. Never push to main.

BACKGROUND
The knowledge-retrieval layer (R0 / T14) was implemented but never tested, and it is broken
in the container. Its contract is docs/AI_KNOWLEDGE_PIPELINE.md — read §2, §3, §5, §7 before
writing code. Baseline: pytest -q = 205 passed, ruff clean. Both must still hold at the end.

Read these before changing anything, and derive exact APIs from the source rather than
guessing signatures: app/engine/knowledge/{types,loader,retrieve}.py, app/engine/pipeline.py,
app/engine/validate.py, knowledge/family/cards.yaml, tests/conftest.py,
tests/test_engine_pipeline.py (fake-provider style), tests/test_deploy_hardening.py
(static-assertion style).

TASK 1 — fix the production bug
Dockerfile copies prompts and rules into the image but not knowledge.
app/engine/knowledge/loader.py resolves the knowledge root to <repo_root>/knowledge, which is
/app/knowledge in the container. That path does not exist in the image, so
FileKnowledgeStore.load() raises KnowledgeLookupError, retrieval returns status="unavailable",
and every production check silently runs with zero knowledge cards — no crash, no alert.
Copy the knowledge directory into the image, in the same style as prompts and rules.

TASK 2 — make the bug impossible to reintroduce
Add a test to tests/test_deploy_hardening.py that reads the Dockerfile as text and asserts
every runtime asset directory the app loads from disk (prompts, rules, knowledge) is copied
into the image. Write it so a fourth asset directory added later fails loudly.

TASK 3 — write tests/test_t14_knowledge.py
(The test_tNN_*.py name matches the repo convention; R0 is T14 in docs/V1_TECHNICAL_PLAN.md.)

asyncio_mode is "auto" — do not add @pytest.mark.asyncio. Inject fakes via
run_check(check_input, session=..., llm_provider=..., knowledge_store=...,
knowledge_router=..., fallback_llm_provider=...). Never hit a network. Where a test depends on
a precondition (e.g. "this text triggers no rules"), assert that precondition inside the test
so it cannot rot into testing nothing.

Cases:
 1. Zero-rule input still reaches the model: text matching no family rule; assert
    result.rule_ids == [], assert the fake LLM was called, assert the check succeeds.
 2. Known-phrasing retrieval: "Мне позвонили и сказали, что из прокуратуры" retrieves
    family.authority_impersonation; assert no verdict wording in the rendered answer.
 3. Inflected phrasing — KNOWN GAP: retrieval matches aliases by plain substring, so
    declensions not literally listed in YAML are missed. Write a test for a different
    inflection (e.g. "Мне звонили, представились прокуратурой") asserting the DESIRED
    behaviour (card retrieved), marked
    @pytest.mark.xfail(reason="substring alias matching misses inflections; awaiting
    semantic router", strict=False). See the prohibition below before touching this.
 4. Rule-triggered card is mandatory: input firing a rule in a card's trigger_rule_ids
    produces that card.
 5. No match still answers: an in-scope input retrieving nothing still calls the LLM; assert
    the knowledge block is empty rather than fabricated.
 6. The three-card ceiling holds even when more cards would match.
 7. Invalid router id is rejected: a fake router returning an id outside the allowlist must
    never reach lookup or the prompt.
 8. Router failure degrades: a fake router that raises must not crash the check.
 9. Knowledge lookup failure degrades: a fake store raising KnowledgeLookupError produces
    retrieval_status="unavailable", still calls the LLM, never claims knowledge was consulted.
10. Provider failure uses the fallback: primary llm_provider raises, fallback_llm_provider
    succeeds; assert a normal successful result, NOT no_signal and not an error status.
11. Validator unit tests: a draft claiming a retrieved case proves the current situation is
    rejected; a draft containing an internal knowledge id is rejected; a draft claiming an
    external database was checked is rejected.
12. No content leaks: after a check, the persisted check_event row and emitted log fields
    contain only ids, enums and metrics — no submitted text, minimized text, prompt or model
    output. Follow tests/test_schema_privacy.py.

PROHIBITIONS — violating any of these fails the task
- Do NOT add, edit or reorder retrieval aliases in knowledge/**/*.yaml to make a test pass.
  Case 3 is a deliberately recorded gap; widening the alias list hides the exact problem this
  suite exists to expose.
- Do NOT weaken prompts/*, the rule packs, or any existing check in app/engine/validate.py.
- Do NOT persist or log submitted content, OCR text, minimized text, prompts or model output.
- Do NOT implement the semantic router — separate task, fakes only.
- Do NOT modify existing passing tests to accommodate new code. If one fails, you caused a
  regression; fix your change, not the test.
- Do NOT edit docs/AI_KNOWLEDGE_PIPELINE.md, especially its §8 audit table.
- No new runtime dependencies. Do not commit, push or open a PR.

DONE WHEN
pytest -q passes with more than 205 tests, zero failures (case 3 reports xfailed, which is
correct); ruff check . clean; Dockerfile copies knowledge and a test enforces it.

REPORT BACK
Test count before/after, ruff result, which cases pass vs xfail, and — most valuable — any
place the implementation behaved differently than this prompt predicted. Describe the
discrepancy rather than quietly adjusting the test to match the code.
```

---

## T-02 — Correct the stale audit table

> **Do this task with full repository context, not blind.** It is small but requires judgment; a model that pattern-matches will get it wrong in both directions.

```
You are working in the Avvalo repository. Branch: launch-features. Never push to main.

docs/AI_KNOWLEDGE_PIPELINE.md §8 contains an implementation audit snapshot dated 2026-07-15.
It is now wrong: it marks several contract areas "❌ Missing" that have since been implemented
(the knowledge card store, rule/signal/cue retrieval, knowledge injection into the answer
prompt, provider fallback, knowledge/version observability). The document's stated purpose is
that documentation must never imply capability that does not exist — right now it does the
mirror image, denying capability that does.

TASK
Re-run the audit against the actual code and rewrite the §8 table. For every row:
- Open the code and verify the claim. Cite the concrete evidence (file, function, or test) in
  the Evidence column, exactly as the existing rows do.
- Use ✅ only where an automated test proves it. Use ⚠️ Partial where code exists but is
  unproven or incomplete, and say precisely what is missing.
- Update the snapshot date to the day you run it.

Two rows need particular care:
- "Allowlisted semantic router" — the KnowledgeRouter protocol and the call site exist, but no
  implementation does. That is ⚠️, not ✅ and not ❌; state the distinction.
- "Safety validator" — knowledge-grounding checks were added, but rule preservation is still
  weak: with multiple high-severity hits, any single non-empty red_flags list passes and
  individual facts are not verified. Keep that gap visible.

Also correct any other line in the file contradicted by the current code.

PROHIBITIONS
- Do not change §1–§7 (the contract itself). Only §8, the audit, is in scope.
- Do not mark anything ✅ on the strength of code reading alone. No test, no ✅.
- Do not soften a gap to make the table look better. This table exists to be uncomfortable.
- Do not change code in this task. Documentation only.

DONE WHEN
Every row's evidence has been verified against the current tree, and someone reading only §8
would form an accurate picture of what works. Report which rows changed and why.
```

---

## T-03 — Knowledge-gap report (the learning loop's sense organ)

**Goal:** let the system tell the founder what it does not know, using only privacy-safe metadata.

**Why now:** after T-01, every check records `retrieval_status`, `knowledge_card_ids` and `rule_ids`, and `feedback` is keyed by `check_id`. That is enough to find the misses without storing a single byte of user content. Without this, writing new cards is guesswork.

**Known limitation to design around, not hide:** this report shows *that* a check missed, never *what* it was about — content is not stored. Pairing a gap count with the consented story corpus (R3) is what turns a number into a card. Say so in the tool's own output.

```
You are working in the Avvalo repository (Python 3.11, async SQLAlchemy, PostgreSQL 16, in-
memory SQLite for tests). Read CLAUDE.md first. Branch: launch-features. Never push to main.

GOAL
Build an operator CLI that reports where the knowledge base failed to help, so the founder
knows which cards to write next. Privacy-safe metadata only.

Read first: app/data/models.py (CheckEvent, Feedback), app/data/repo.py, app/tools/ (match the
existing operator CLI module style exactly — argument parsing, session handling, output), and
app/engine/knowledge/retrieve.py for the retrieval_status vocabulary.

BUILD
A CLI in app/tools/ that takes a date range (default: last 7 days) and an optional face, and
prints:
 1. Coverage — share of checks where retrieval found at least one card, broken down by face
    and language. Report retrieval_status="unavailable" as a SEPARATE line, never merged into
    "no match": one means the knowledge base had nothing to say, the other means it was
    unreachable. Conflating them hides outages.
 2. Gap list — checks where retrieval returned nothing AND the user's feedback was negative,
    grouped by (face, language, rule_ids). This is the card backlog, most frequent first.
 3. Card usage — how often each card was selected, and which approved cards were never
    selected at all in the window. Unused cards are either badly worded or badly targeted.
 4. Router health, once T-05 lands — counts by retrieval_mode, and how often invalid ids were
    rejected. Write the query so this section is empty rather than broken before then.

Print a short footer stating plainly that submitted content is not stored, so this report
shows where the system missed but not what the message said, and that identifying the pattern
requires the consented story corpus.

CONSTRAINTS
- Read-only. This tool must never write to the database.
- Select only allowlisted metadata columns. If you find yourself selecting a text column that
  could hold user content, stop — that is a bug in the schema, report it instead.
- Every tunable via Settings (app/config.py) + .env.example. Never hardcode.
- Add tests using the in-memory SQLite session fixture in tests/conftest.py: seed events and
  feedback, assert the aggregates. Include a case with zero rows (must not divide by zero) and
  a case mixing "unavailable" with "no match" (must not merge them).

DONE WHEN
pytest -q and ruff check . are clean, the CLI runs against a seeded local database, and the
output is readable by a human deciding what to write next — not a raw table dump.
Report the command line you ran and paste its output.
```

---

## T-04 — Coverage and time-to-card metrics

**Goal:** two numbers that say whether the system is actually getting smarter.

```
You are working in the Avvalo repository. Read CLAUDE.md first. Branch: launch-features.
Never push to main.

GOAL
Make "is the system improving?" answerable from the daily metrics line instead of intuition.

Read first: app/obs/ (the existing metrics/events modules and the daily metrics line),
app/engine/knowledge/loader.py (card versions), knowledge/version.yaml.

BUILD
 1. Knowledge coverage — add to the existing daily privacy-safe metrics line: share of checks
    where at least one card was selected, and separately the share where retrieval was
    unavailable. Follow the existing metric conventions; do not invent a new output format.
 2. Card inventory — expose the loaded knowledge base version and approved-card count per face
    at startup and in the metrics line, so a version bump is visible in logs without shell
    access. This is how you confirm a card actually reached production.
 3. Alert threshold — extend the existing alerting in app/obs/alerts.py so a sustained spike in
    retrieval_status="unavailable" raises an alert, exactly like the existing error alerts. The
    T-01 bug went unnoticed because nothing watched this; make it noticeable now. Threshold and
    window via Settings + .env.example.

CONSTRAINTS
- Metrics carry ids, enums, counts and versions only. Never content.
- Reuse the existing metrics and alerting machinery. Do not add a parallel system.
- Tests: seed events, assert the computed shares; assert the alert fires above the threshold
  and stays quiet below it.

NOT IN SCOPE
Time-to-card (hours from a pattern appearing to a card shipping) is a founder-tracked number,
not a computable one — the system cannot know when a scam started circulating. Do not attempt
to derive it. Mention in your report that it belongs in the weekly review, not in code.

DONE WHEN
pytest -q and ruff check . clean; the metrics line shows coverage and kb version; the alert has
a test proving both directions.
```

---

## T-05 — Semantic router

**Goal:** close the recall gap that substring aliases structurally cannot close, and flip T-01's `xfail` to green.

**Design constraint that decides this task:** the router is a *recall* mechanism, not a judgement mechanism. It proposes card ids from a server-supplied allowlist. It never sees raw text, never emits red flags, and never decides anything the user sees.

```
You are working in the Avvalo repository. Read CLAUDE.md first, then
docs/AI_KNOWLEDGE_PIPELINE.md §3 ("Semantic router") and §4, and
docs/V1_TECHNICAL_PLAN.md §8.1. Branch: launch-features. Never push to main.

PROBLEM
Retrieval matches card aliases by plain substring on normalized text
(app/engine/knowledge/retrieve.py). Russian and Uzbek are inflected, so any declension not
literally listed in the YAML is missed: "из прокуратуры" is listed and matches,
"прокуратурой" is not and does not. Widening alias lists is not a fix — it is memorising the
test set. tests/test_t14_knowledge.py has an xfail case recording exactly this gap.

BUILD
 1. app/engine/knowledge/router.py implementing the existing KnowledgeRouter protocol (read
    app/engine/knowledge/types.py for the exact contract; do not guess). Use the existing
    OpenAI-compatible adapter — do not add a new client or dependency.
 2. Config in Settings + .env.example + deploy/env.prod.example: enabled flag (default off),
    base url, api key, model, timeout. Default-off means production behaviour is unchanged
    until the founder turns it on deliberately.
 3. Wire it in app/engine/pipeline.py the same way llm_provider is wired: injectable, built
    from settings when not supplied. The call site in retrieve_knowledge already exists.
 4. Router tokens must be added to the check's cost accounting. Read app/obs/cost.py and
    docs/V1_TECHNICAL_PLAN.md §8.1 — the contract requires aggregating router and answer-model
    tokens. A check that silently costs double is a budget bug.

FIX TWO EXISTING DEFECTS while you are in retrieve.py
 a. When deterministic retrieval returns MORE than the three-card ceiling, the router is
    consulted but its ids are appended after the deterministic ranking and then truncated
    away — so the call is paid for and discarded. Either use the result meaningfully in that
    branch or do not call the router there at all. State which you chose and why.
 b. status="invalid_router_ids" currently overwrites the status even when good deterministic
    cards were selected, so a successful retrieval reports as a failure. Separate "what was
    retrieved" from "did the router misbehave".

HARD CONSTRAINTS
- The router receives MINIMIZED text only. Never raw text, never the image. If you cannot show
  this from the call site, the task is not done.
- It returns only ids from the allowlist the backend supplied, plus an unmatched option. The
  backend already validates; do not move validation into the model.
- Router output must never become a red flag, a verdict, or anything the user sees. It selects
  context, nothing more.
- Router failure or timeout must degrade to deterministic retrieval and still run the answer
  model. Never fail the check because recall failed.
- Do not add embeddings, a vector database, or any new runtime dependency.
- Do not edit knowledge/**/*.yaml aliases in this task.

TESTS
Fake router for logic; real router class tested against a fake LLM provider. Cover: invalid id
rejected; router not called when deterministic retrieval already succeeded; router called on
empty retrieval; timeout degrades; minimized text only; cost includes router tokens. Then
remove the xfail marker from the inflection case in tests/test_t14_knowledge.py and confirm it
passes for real. If it does not, report that instead of loosening the assertion.

DONE WHEN
pytest -q and ruff check . clean; the previously-xfailed inflection case passes; the router is
off by default; a check with the router disabled behaves exactly as before.
```

---

## T-06 — Validator: per-fact rule preservation

**Goal:** close the gap the project's own audit names — "with multiple high-severity hits, any single non-empty `red_flags` list passes; individual facts are not verified."

**Why this is hard, and the recommended approach:** rule descriptions are neutral English, the answer is Uzbek or Russian, so string matching cannot verify preservation. The clean fix is structural: have the model declare which rule ids it addressed, and validate that set deterministically.

```
You are working in the Avvalo repository. Read CLAUDE.md first, then
docs/V1_TECHNICAL_PLAN.md §9 (safety validator) and docs/AI_KNOWLEDGE_PIPELINE.md §3
("Validator"). Branch: launch-features. Never push to main. This is safety-critical code —
prefer rejecting a good answer over accepting a bad one.

PROBLEM
app/engine/validate.py computes requires_red_flag = any(hit.severity >= threshold ...) and then
accepts any non-empty red_flags list. So when three high-severity rules fire and the model
mentions only one, validation passes and two authoritative facts are silently dropped. The
contract says every rule-grade fact must survive into the answer.

RECOMMENDED APPROACH (deviate only if you find something better, and say why)
Extend DraftOutput in app/engine/types.py with a field where the model declares the rule ids it
addressed. Update the JSON schema, prompts/system_safety.txt and the face templates so the
model must return it. Then validate deterministically: every high-severity rule hit must appear
in the declared set. On failure, use the existing corrective-retry path with a reason naming
the missing ids; on second failure, the existing safety fallback.

This is language-independent, which is the whole point — it works identically for uz_latn,
uz_cyrl and ru without string matching.

CONSTRAINTS
- The model declaring a rule id is not proof it discussed it. Treat this as a floor that
  catches the common failure (silently dropping facts), not as a guarantee. Say so in the
  module docstring rather than overclaiming.
- Extend prompts/*; do not weaken or remove any existing prohibition.
- Do not change the no_signal rule: no_signal stays (no rule hits AND no red flags). A model
  must never be pushed to invent a flag to satisfy this check.
- Boundary types are Pydantic (app/engine/types.py) — extend those, do not pass loose dicts.
- Backward compatibility: existing golden fixtures in tests/fixtures/golden/ must still pass.
  If they cannot, report it before changing fixture files.

TESTS
Three high-severity hits with only one addressed → rejected. All addressed → accepted. Zero
hits → unchanged behaviour. Retry path exercised. Fallback on second failure. All three
languages.

DONE WHEN
pytest -q and ruff check . clean; the new check has tests in both directions; docstrings cite
the spec section per repo convention.
```

---

## T-07 — URL reputation stage (R6)

Already specified — do not rewrite the design. Point the executor at the existing spec:

```
Read docs/LAUNCH_EXECUTOR_PROMPT.md and execute task R6 only. Also read
docs/ML_RESEARCH.md §4 for why it is shaped that way, and docs/PRODUCT_GUIDE.md for the safety
rules that override everything.

Key constraint restated because it is easy to get wrong: the blocklist line is permitted only
because it is a sourced statement of fact about a URL — an artifact, not a person — phrased as
"appears in a public phishing blocklist", never "this is a scam". It is the single exception to
the no-database-claims rule and it does not generalise. If you find yourself extending that
phrasing to anything other than a URL, stop.

Branch: launch-features. Never push to main. pytest -q and ruff check . green at the end.
```

---

## Not engineering tasks — but they decide whether any of this matters

Listed here so they are not lost between code sessions. **Founder only.**

- **Phase A production verification.** [ROADMAP.md](ROADMAP.md) Phase A smoke evidence is still unrecorded while feature work continues on top. Verify the live deployment and write it down.
- **Weekly card review.** Read the T-03 gap report, write one to three cards, bump the version. Thirty minutes. This is the actual learning loop — the code above only makes it visible and fast.
- **Users.** Coverage percentages over zero checks are zero information. Every automated improvement above ranks below this and does not compete with it for time.
