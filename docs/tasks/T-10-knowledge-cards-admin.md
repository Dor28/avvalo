---
id: T-10
title: Add the operator-only knowledge card editor with a retrieval dry-run
status: done
owner: claude
branch: claude/knowledge-cards-admin
size: 1d
depends_on: [T-09]
blocks: []
created: 2026-07-22
---

# T-10 — Add the operator-only knowledge card editor with a retrieval dry-run

> **Handoff:** `Read docs/tasks/T-10-knowledge-cards-admin.md and do it.`

## BACKGROUND

T-09 moves knowledge cards into `knowledge_card_override` and merges them onto the shipped YAML
baseline. Until this task lands there is no way to write a card except by hand-editing the
database, so the storage layer is not yet usable by the founder.

This mirrors `/admin/rules`, which was built for the rule pack in the same way. The admin surface
already exists and is authenticated: `app/web/admin_auth.py` issues a short-lived signed HttpOnly
cookie, every `/admin` route 404s unless `ADMIN_ACCESS_KEY` is configured, and
`app/web/abuse.py:require_same_origin` guards every mutating POST. Reuse all of it; do not invent
a second auth path.

What makes this screen different from the rule editor: a card does not merely match text, it
**changes what the model is told**. A card can be well-formed, save cleanly, and still never be
retrieved — because retrieval is driven by `trigger_rule_ids`, `trigger_signal_kinds`, and
`retrieval_aliases`, not by the card body. An operator who writes a good card with a typo'd rule ID
gets silence, not an error. The dry-run is what makes that visible, and it is the reason this task
exists as more than a CRUD form.

Two constraints carried forward from T-09, restated because they are easy to get wrong here:

- **Card bodies are English.** `mechanism`, `red_flags`, `verify_steps`, `questions` are English
  text handed to the LLM. Only `retrieval_aliases` are per-language (`uz_latn` / `uz_cyrl` / `ru`).
  The editor's own labels and messages must exist in all three languages; the card body fields must
  not be triplicated.
- Retrieval returns **at most three** cards, and `app/engine/llm/prompt.py:88` raises above three.

Baseline: `pytest -q` = **314 passed** on `main` at the time of writing, plus whatever T-09 adds.
Measure it yourself after merging T-09 and use that number. `ruff check .` clean.

## READ FIRST

- `docs/AI_KNOWLEDGE_PIPELINE.md` §4 (retrieval rules), §7 (acceptance criteria)
- `app/knowledge_store/` — everything T-09 created; `repo.py` for the draft type and its validation
  error keys, `apply.py` for `refresh_knowledge_base()`
- `app/engine/knowledge/retrieve.py` — `retrieve_knowledge()`; the dry-run calls this, see TASK 2
- **Prior art to mirror, closely:**
  - `app/web/rules_admin.py` — route shapes, `_draft_from_form`, `_form_response`, the
    `_admin_settings` / `_require_admin` / `_no_store` helpers
  - `app/web/rules_copy.py` — the trilingual copy structure, including the `errors` sub-dict keyed
    by the `ValueError` codes the repo raises
  - `app/web/templates/admin_rules.html`, `admin_rule_form.html` — markup and existing CSS classes
    (`admin-editor-form`, `admin-settings-card`, `admin-field`, `admin-form-error`,
    `admin-dry-run`, `admin-dry-run-result`)
  - `app/web/templates/_admin_header.html` — the section nav; note `rules_nav_label` is passed from
    **both** `editorial.py` and `rules_admin.py` contexts because Jinja renders an undefined name
    as an empty string
  - `tests/test_rules_admin.py` — the test style to match, including the fixture that creates
    `Base`, `RuleStoreBase`, and `EditorialBase` tables
- `app/web/app.py:42-44` — routers are wired by extending `web_app.router.routes`, not
  `include_router`

## TASK 1 — Build the CRUD surface

Add `app/web/knowledge_admin.py` and `app/web/knowledge_copy.py`, plus templates
`admin_cards.html` and `admin_card_form.html`. Routes, matching `/admin/rules`:

| Route | Method | Purpose |
|---|---|---|
| `/admin/cards` | GET | list overrides, with the YAML baseline count |
| `/admin/cards/new` | GET | empty editor |
| `/admin/cards/{id}/edit` | GET | populated editor |
| `/admin/cards` | POST | create or update, then republish |
| `/admin/cards/preview` | POST | dry-run, saves nothing |
| `/admin/cards/{id}/delete` | POST | delete, restoring the YAML card |

List and array fields (`red_flags`, `verify_steps`, `questions`, `trigger_rule_ids`,
`trigger_signal_kinds`, and each language's `retrieval_aliases`) are one entry per line in a
textarea, as `_split_patterns` does in `rules_admin.py`.

Show the card's `status` (`approved` / `draft` / `retired`) as a select, and state in the copy that
only `approved` reaches retrieval — otherwise an operator will save a `draft` and wonder why
nothing happens.

Register the router in `app/web/app.py` and add a third link to `_admin_header.html`, passing the
new nav label from **all three** context builders (`editorial.py`, `rules_admin.py`, and the new
module). Assert the label renders, as `tests/test_rules_admin.py` does — a missing context key
fails silently.

Saving and deleting must call `refresh_knowledge_base()` before returning, so the edit is in force
immediately rather than after `KNOWLEDGE_REFRESH_MINUTES`.

## TASK 2 — Make the dry-run answer the question that matters

The dry-run takes sample text and reports **whether this card would actually be retrieved for it**.

**Decision — drive the preview through the real `retrieve_knowledge()`, not a reimplementation.**
Build the candidate `KnowledgeBase` by merging the unsaved draft over the current base in memory,
pass it via a throwaway in-memory `KnowledgeStore` (the `store=` parameter already exists on
`retrieve_knowledge`), and call it with the sample text. The rule hits and signals for the sample
come from `run_rules(sample, face)` so the trigger fields are exercised for real. A preview that
reimplemented cue matching would drift from production and give false confidence — this is the same
reason `matching_patterns()` was extracted for the rule editor.

Report, in the operator's language:

- whether the card was selected, and the `RetrievalResult.mode` that selected it
  (`rule` / `signal` / `cue` / `router` / `none`);
- **if it was not selected, say so explicitly** — this is the common case the screen exists for;
- which other card IDs were selected instead, so a three-card cap collision is visible;
- if the card's `status` is not `approved`, say that this alone is why it was not retrieved.

The router must not be invoked during a preview; pass `router=None` so the dry-run is deterministic
and free.

## TASK 3 — Tests

New `tests/test_knowledge_admin.py`, matching `tests/test_rules_admin.py`:

- signed-out requests to every route redirect to `/admin/login`;
- all routes 404 when `admin_access_key` is unset;
- a cross-origin POST is rejected;
- the header exposes all three admin sections and their labels actually render;
- preview with a matching `trigger_rule_ids` reports selection **and persists nothing**;
- preview of a card that cannot be retrieved for the sample reports non-selection;
- preview of a `draft` card reports the status as the reason;
- saving republishes immediately: `retrieve_knowledge()` returns the new card ID without waiting
  for the refresh job;
- an invalid draft is rejected with a localized message and is not persisted;
- a duplicate card ID is reported rather than raising;
- deleting an override restores the YAML baseline card.

## PROHIBITIONS — violating any of these fails the task

- Do **NOT** reimplement retrieval scoring inside the preview. A dry-run that disagrees with
  production is worse than no dry-run, because it will be trusted. Call `retrieve_knowledge()`.
- Do **NOT** let the preview reach the semantic router or any LLM provider. It must be
  deterministic and must cost nothing.
- Do **NOT** make the preview write to the database, or "temporarily" save-then-roll-back to
  produce it. Merge in memory.
- Do **NOT** report "no match" and "card is not approved" with the same message. Collapsing them
  is the shortcut that makes the tests pass while leaving the operator unable to tell why their
  card is silent — which is the entire point of this screen.
- Do **NOT** build a second admin authentication path, session cookie, or access-key check. Reuse
  `app/web/admin_auth.py` and `require_same_origin`.
- Do **NOT** triplicate the English card body fields into three languages. The editor's own labels
  and error strings must exist in all three; the card body must not.
- Do **NOT** allow more than three cards into a prompt, or relax `_render_knowledge`'s guard, to
  make a preview case look better.
- Do **NOT** weaken `prompts/*`, the rule packs, or existing checks in `app/engine/validate.py`.
- Do **NOT** persist or log submitted content, OCR text, minimized text, prompts, or model output.
  The dry-run sample text is submitted content: it must not be written to any row or log.
- Do **NOT** modify existing passing tests to accommodate new code. If one fails, you caused a
  regression; fix your change, not the test.
- No new runtime dependencies. Do not commit, push, or open a PR.

## DONE WHEN

- `pytest -q` passes with more tests than the post-T-09 baseline you measured, zero failures
- `ruff check .` clean
- `grep -rn "retrieve_knowledge" app/web/knowledge_admin.py` returns a hit — the preview uses the
  real retrieval path
- `grep -rn "router=None" app/web/knowledge_admin.py` returns a hit — the preview cannot call the
  router
- A test asserts a preview leaves `knowledge_card_override` empty
- A test asserts the non-selection message and the not-approved message are **different strings**
- `python - <<'PY'` style check, or an equivalent test, confirms every key in
  `app/web/knowledge_copy.py` exists under all three of `uz_latn`, `uz_cyrl`, `ru`
- Starting the app with `ADMIN_ACCESS_KEY` set and visiting `/admin/cards` renders the list; with
  it unset the route returns 404
