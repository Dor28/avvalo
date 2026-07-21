---
id: T-NN
title: <short imperative phrase>
status: open           # open | in_progress | blocked | done | cancelled
owner: unassigned      # unassigned | claude | codex | founder
branch: <branch to work on>
size: <1h | 0.5d | 1d | 2-3d>
depends_on: []         # e.g. [T-05] — do not start until these are done
blocks: []             # e.g. [T-09] — tasks waiting on this one
created: YYYY-MM-DD
---

# T-NN — <title>

> **Handoff:** `Read docs/tasks/T-NN-<slug>.md and do it.`

## BACKGROUND

<Why this exists and what is currently true. State the problem in terms of observable
behaviour, not intent. If something is broken, say what happens today and why it is not
noticed. Cite the contract doc that governs this area.>

Baseline: `pytest -q` = **N passed**, `ruff check .` clean. Both must still hold at the end.

## READ FIRST

<Exact paths, not descriptions. Derive APIs from the source rather than guessing signatures.>

- `path/to/contract.md` §N, §M — the governing contract
- `app/...` — the code you are changing
- `tests/test_....py` — the style to match

## TASK 1 — <imperative>

<What to change. Be specific about files. Where a decision is open, say which way to go and
why, so the agent does not invent a third option.>

## TASK 2 — <imperative>

<...>

## PROHIBITIONS — violating any of these fails the task

<Task-specific traps first, then the standing ones that apply here. The point of this section
is to name the shortcuts that would make the tests pass while defeating the purpose.>

- Do NOT <the specific shortcut that would fake success>
- Do NOT weaken `prompts/*`, the rule packs, or existing checks in `app/engine/validate.py`
- Do NOT persist or log submitted content, OCR text, minimized text, prompts or model output
- Do NOT modify existing passing tests to accommodate new code. If one fails, you caused a
  regression; fix your change, not the test
- No new runtime dependencies. Do not commit, push or open a PR

## DONE WHEN

<Machine-checkable statements only. "Works well" is not a criterion. Name the command and the
expected result.>

- `pytest -q` passes with more than N tests, zero failures
- `ruff check .` clean
- <the specific artifact or behaviour that proves the task landed>
