# AGENTS.md

Instructions for any coding agent working in this repository (Codex, Cursor, Copilot, and
others). Claude Code additionally reads [CLAUDE.md](CLAUDE.md).

**[CLAUDE.md](CLAUDE.md) is the canonical instruction file — read it before you write code.**
It covers the architecture, the commands, the pipeline stages, and the conventions. This file
exists so that agents which do not read `CLAUDE.md` automatically still get the rules that must
never be broken.

## Non-negotiables

These are enforced by tests that fail the build. Violating one is a failed task, not a style
nit.

1. **Submitted content is never persisted or logged.** `raw_text` / `image_bytes` / `caption`
   on `CheckInput` are ephemeral. `check_event` rows and `log_event()` output carry only IDs,
   enums, rule IDs, and metrics. `story_submission.minimized_text` is a legacy stewardship-only
   exception: no new product flow may write or read it, and the old rows remain reachable only for
   `/delete_my_data` and retention until a separately authorized data purge.
2. **No verdicts, no risk scores.** The product verifies the *situation, never the person*, and
   never outputs "safe" / "scam" / "fraud confirmed" in any language. Enforced deterministically
   in [app/engine/validate.py](app/engine/validate.py). Decisiveness belongs in the recommended
   *action* ("do not enter your card here — open the bank's app yourself"), never in a claim
   about the object.
3. **Never claim an external database was checked.**
4. **Never open a submitted destination.** No code path may fetch, render, or execute a submitted
   URL or QR destination. The single bounded exception is shortener redirect resolution
   ([docs/PRODUCT_GUIDE.md](docs/PRODUCT_GUIDE.md) §8.1): `HEAD` only, `https` and public
   addresses only, capped hops, no cookies, on an explicit user action, separate egress, and the
   result is never persisted, logged, or sent to a model. Do not widen it into fetching page
   content.
5. **Do not weaken the safety layer** — `prompts/*`, the rule packs under `rules/`, or existing
   checks in `app/engine/validate.py`. Extend; do not rewrite.
6. **Do not modify a passing test to accommodate new code.** If a green test goes red, you
   caused a regression — fix the change, not the test.
7. **Never push to `main` without explicit founder authorization.** Pushing to `main` deploys to
   production (`.github/workflows/deploy.yml`). Work on a branch.
8. **Every user-facing string exists in both languages** — `uz_latn` and `ru`. Uzbek is replied
   to in Latin script **today**; Cyrillic-Uzbek *output* is scheduled work in
   [docs/ROADMAP.md](docs/ROADMAP.md), not a permanent boundary. Cyrillic-Uzbek input is already
   read and matched by the `uz_cyrl` keyword groups in the rule packs.
9. **There is one checker and no product-face concept:** the `face` discriminator was removed from the code and the database. Merchant
   payment situations use the same checker and safety pipeline. Do not restore Avvalo Merchants,
   the scam library, story capture, Scam Pulse, or another face from git history. The approved
   wave notification is **not** Scam Pulse: it is a founder-authored push, two or three a month,
   never an aggregate trend feed and never derived from user submissions.

## Definition of done

```bash
pytest -q          # all green; no fewer tests than the baseline stated in your task
ruff check .       # clean
```

No new runtime dependencies unless the task says so. Do not commit, push, or open a PR unless
the task says so.

## Where the work is defined

Task prompts live in [docs/tasks/](docs/tasks/) — one file per task, self-contained. If you were
handed a task file, that file plus this one plus `CLAUDE.md` is everything you need.
[docs/tasks/README.md](docs/tasks/README.md) explains the format and holds the index.
