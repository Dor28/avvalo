---
id: T-09
title: Move knowledge cards into the database behind the existing sync store protocol
status: done
owner: claude
branch: claude/knowledge-cards-store
size: 1d
depends_on: []
blocks: [T-10]
created: 2026-07-22
---

# T-09 — Move knowledge cards into the database behind the existing sync store protocol

> **Handoff:** `Read docs/tasks/T-09-knowledge-cards-store.md and do it.`

## BACKGROUND

The repository is public (`github.com/Dor28/avvalo`). `knowledge/checker/cards.yaml` is therefore
readable by the people the cards describe, and every future card is published on push. The rule
pack has already been moved out of git for this reason — `app/rules_store/` layers operator-authored
patterns onto the shipped YAML baseline, and this task applies the same pattern to knowledge cards.

What is true today:

- `FileKnowledgeStore.load(face_id)` reads `knowledge/<subdir>/*.yaml` plus `knowledge/version.yaml`
  and returns a `KnowledgeBase`. It is **synchronous** and `@cache`d
  (`app/engine/knowledge/loader.py`).
- `KnowledgeStore` is a `Protocol` with `def load(self, face_id: str) -> KnowledgeBase` — sync.
  It is called from `retrieve_knowledge()` (`app/engine/knowledge/retrieve.py:31`), from
  `app/obs/metrics.py:76,186`, and from `app/tools/knowledge_gaps.py:95`.
- Only cards with `status == "approved"` are returned; `draft` and `retired` are dropped by the
  loader. `_validate_card` rejects a card whose `face` does not match the requested face.
- Retrieval is capped at three cards, and `_render_knowledge` in `app/engine/llm/prompt.py:88`
  **raises** if more than three reach the prompt.

Two findings that shape the implementation:

1. **`kb_version` is validated on write.** `app/data/repo.py:207` rejects any `kb_version` that
   fails `VERSION_RE = ^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$`. A database-derived version string that
   contains `+`, a space, or a colon will make **every `record_check_event` call raise**, which
   fails every check after the model has already been paid for. Note that `-` and `.` are allowed
   and `:` and `+` are not.
2. **Card bodies are English; only `retrieval_aliases` are per-language.** `mechanism`,
   `red_flags`, `verify_steps`, and `questions` are English text handed to the LLM as guidance —
   see `knowledge/checker/cards.yaml`. Do not force them into three languages. The three-language
   rule in `AGENTS.md` applies to user-facing strings, and card bodies never reach the user
   verbatim.

Governing contract: `docs/AI_KNOWLEDGE_PIPELINE.md` §4 (retrieval rules), §5 (failure behaviour),
§6 (versioning), §7 (acceptance criteria).

Baseline: `pytest -q` = **314 passed**, `ruff check .` clean. Both must still hold at the end.

## READ FIRST

- `docs/AI_KNOWLEDGE_PIPELINE.md` §4, §5, §6, §7 — the governing contract
- `app/engine/knowledge/loader.py` — `FileKnowledgeStore`, `_load_knowledge_base`,
  `clear_knowledge_cache`, `_validate_card`
- `app/engine/knowledge/types.py` — `KnowledgeCard`, `KnowledgeBase`, `KnowledgeStore`,
  `KnowledgeLookupError`
- `app/engine/knowledge/retrieve.py` — the only product consumer; note the
  `KnowledgeLookupError → status="unavailable"` path at line 31
- `knowledge/checker/cards.yaml`, `knowledge/version.yaml` — the current baseline and its version
- `app/data/repo.py:45,207` — `VERSION_RE` and the `kb_version` check described above
- **Prior art to mirror, closely:**
  - `app/rules_store/models.py` — separate declarative base, and why
  - `app/rules_store/repo.py` — draft validation, `load_overrides()`
  - `app/rules_store/apply.py` — `merge_rule_pack()`, `refresh_rule_pack()`,
    `install_rule_pack_refresh_job()`
  - `app/engine/rules/loader.py:43-67` — the sync snapshot pattern (`load_rule_pack`,
    `set_active_rule_pack`, `clear_active_rule_packs`)
  - `tests/test_rule_overrides.py` — the test style to match
- `tests/test_schema_privacy.py:32,46` — `EXPECTED_TABLES` is an **exact-equality** assertion over
  `app.data.models.Base`; see PROHIBITIONS
- `alembic/env.py` — `target_metadata` is a list of metadata objects; head revision is
  `0007_rule_overrides`

## TASK 1 — Add the storage layer

Create `app/knowledge_store/` with `models.py`, `repo.py`, `apply.py`, `__init__.py`, mirroring
`app/rules_store/`.

**Decision — use a new `KnowledgeStoreBase` declarative base, not `Base` and not `RuleStoreBase`.**
`Base` is impossible (see PROHIBITIONS); a separate base keeps the "rules store" name from owning
knowledge rows. This is the third instance of an established pattern — `EditorialBase`,
`RuleStoreBase`, now `KnowledgeStoreBase`.

Table `knowledge_card_override`, one row per card, carrying every `KnowledgeCard` field:
`face`, `card_id` (unique with `face`), `version`, `status`, `reviewer`, `trigger_rule_ids`,
`trigger_signal_kinds`, `retrieval_aliases`, `mechanism`, `red_flags`, `verify_steps`,
`questions`, `reviewed_case_ids`, plus `created_ts` / `updated_ts`. Use `JSON` for the list and
dict columns, as `app/rules_store/models.py` does for `patterns`.

Validate on write in `repo.py`: card ID shape, `face` in `FACES`, `status` in
`{approved, draft, retired}`, non-empty `mechanism` and `reviewer`, `retrieval_aliases` keys
restricted to `uz_latn` / `uz_cyrl` / `ru`, and sane length caps. A row that fails validation at
**load** time must be skipped, not raised — one bad row must not drop the whole base to YAML.

Add Alembic revision `0008_knowledge_card_overrides` with `down_revision = "0007_rule_overrides"`,
and register `KnowledgeStoreBase.metadata` in `alembic/env.py`.

## TASK 2 — Merge onto the YAML baseline behind the existing sync protocol

In `apply.py`, implement merge-by-card-ID exactly as `merge_rule_pack` does:

- a DB row whose `card_id` matches a YAML card **replaces** it;
- a new `card_id` **adds** a card;
- `status` of `draft` or `retired` **suppresses** the YAML card of that ID, because the loader
  already drops non-approved cards.

Keep `KnowledgeStore.load()` synchronous. Add a process-level snapshot to
`app/engine/knowledge/loader.py` in the shape of `app/engine/rules/loader.py:43-67`: a
`set_active_knowledge_base()` / `clear_active_knowledge_bases()` pair, with `FileKnowledgeStore`
(or a new default store) returning the published snapshot when one exists and the YAML base
otherwise. **Do not change the `KnowledgeStore` protocol signature** — three call sites and the
`UnavailableKnowledgeStore` test double depend on it.

Add `refresh_knowledge_base(session, face_id)` and an
`install_knowledge_refresh_job(scheduler, session_factory, settings)` following
`install_rule_pack_refresh_job`, wired in `app/main.py` next to it. Add
`KNOWLEDGE_REFRESH_MINUTES` to `Settings`, `.env.example`, and `deploy/env.prod.example`.

## TASK 3 — Derive a `kb_version` that survives validation

When any override contributes to the merged base, the published `kb_version` must change so
telemetry can tell which knowledge answered a check, and it must match
`^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$`.

**Decision — use `f"{yaml_version}.db{latest_updated_ts:%Y%m%d%H%M%S}"`**, where `latest_updated_ts`
is the newest `updated_ts` among contributing rows; fall back to the unchanged YAML version when
there are no overrides. Dots and digits are inside the allowed character class and the result stays
well under 80 characters. Do not use `+`, `:`, or a space.

Add a test that feeds the derived version through
`app.data.repo.record_check_event(..., kb_version=...)` and asserts it is accepted — a unit
assertion against the regex alone would not catch a change to `VERSION_RE`.

## TASK 4 — Tests

New `tests/test_knowledge_overrides.py`, matching the structure of `tests/test_rule_overrides.py`:

- `KnowledgeStoreBase.metadata.tables` contains only the new table, and that table is **not** in
  `app.data.models.Base.metadata`;
- write validation rejects each invalid field, one parametrised case each;
- merge: replace by ID, add by new ID, `retired`/`draft` suppresses a YAML card;
- an unreachable database leaves the previously published base in force, and a cold process falls
  back to the YAML baseline rather than to an empty base;
- one malformed row is skipped while the rest of the base still loads;
- end to end: a stored override reaches `retrieve_knowledge()` and appears in
  `RetrievalResult.knowledge_card_ids`;
- the derived `kb_version` is accepted by `record_check_event`.

Update `docs/AI_KNOWLEDGE_PIPELINE.md` §6 and `docs/V1_TECHNICAL_PLAN.md` §6 to describe the
override layer, in the style of the §5.1 section added for rule overrides.

## PROHIBITIONS — violating any of these fails the task

- Do **NOT** put the new table on `app.data.models.Base`. `tests/test_schema_privacy.py:46`
  asserts `set(Base.metadata.tables) == EXPECTED_TABLES` by exact equality, so doing this turns the
  suite red — and **editing `EXPECTED_TABLES` to make it green is the specific shortcut this
  prohibition exists to forbid.** That test is the zero-content contract; the correct move is a
  separate declarative base, as `EditorialBase` and `RuleStoreBase` already do.
- Do **NOT** delete, empty, or stop reading `knowledge/checker/cards.yaml`. It is the fallback
  baseline. A database-only source means an unreachable database silently produces an **empty**
  knowledge base, and `retrieve_knowledge` would then return `status="empty"` rather than
  `"unavailable"` — the pipeline would look healthy while answering with no knowledge at all.
  §5 of the contract requires degradation to be visible.
- Do **NOT** change `KnowledgeStore.load()` to `async`, or otherwise alter the protocol signature,
  to avoid implementing the snapshot. It would cascade into `retrieve.py`, `metrics.py`, and
  `knowledge_gaps.py` for no product gain.
- Do **NOT** load `draft` or `retired` cards into retrieval to make a test pass. Only `approved`
  cards may reach the prompt.
- Do **NOT** raise the three-card retrieval cap or relax `_render_knowledge`'s guard.
- Do **NOT** weaken `_validate_card`, the face check, `prompts/*`, the rule packs, or existing
  checks in `app/engine/validate.py`.
- Do **NOT** drop `kb_version` from the event payload, or make it a constant, to sidestep TASK 3.
- Do **NOT** persist or log submitted content, OCR text, minimized text, prompts, or model output.
  Card rows are operator-authored reference data and must never be written from a check.
- Do **NOT** modify existing passing tests to accommodate new code. If one fails, you caused a
  regression; fix your change, not the test.
- No new runtime dependencies. Do not commit, push, or open a PR.

## DONE WHEN

- `pytest -q` passes with **more than 314** tests and zero failures
- `ruff check .` clean
- `python -m alembic history` shows `0007_rule_overrides -> 0008_knowledge_card_overrides (head)`
- `grep -rn "knowledge_card_override" tests/test_schema_privacy.py` returns **nothing**, and
  `git diff --stat tests/test_schema_privacy.py` is empty — the privacy test is untouched
- `knowledge/checker/cards.yaml` still exists and still loads: with no rows in
  `knowledge_card_override`, `FileKnowledgeStore().load("family")` returns the same card IDs as on
  `main`
- A test named for the fallback asserts that a store failure yields `RetrievalResult(status=...)`
  of `unavailable`, not `empty`
- `grep -n "KNOWLEDGE_REFRESH_MINUTES" .env.example deploy/env.prod.example app/config.py` returns
  a hit in all three
