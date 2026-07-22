# Task queue — executor-ready prompts, one file per task

Each file in this directory is a **self-contained prompt for one coding agent in one session**.
Hand an agent the path and nothing else:

```
Read docs/tasks/T-08-example.md and do it.
```

The agent reads that file, plus [AGENTS.md](../../AGENTS.md) (or [CLAUDE.md](../../CLAUDE.md)),
and has everything it needs. Task files are plain Markdown with no tool-specific syntax — they
work equally for Claude Code, Codex, or a human.

## Index

| ID | Task | Status | Owner | Branch | Depends on |
|---|---|---|---|---|---|
| — | _no open tasks yet_ | | | | |

Do not create an Avvalo Verify implementation task until Phase B in
[ROADMAP.md](../ROADMAP.md) records a `go` decision.

Statuses: `open` · `in_progress` · `blocked` · `done` · `cancelled`.
The frontmatter in each file is the source of truth; this table is a convenience view — update
both in the same commit.

## Rules

- **One task per session.** Two tasks in one session share files and the review gets muddy.
- **Check `depends_on` before starting.** If a dependency is not `done`, the task is not ready.
- **The file is the contract.** If an agent needs information that is not in the file, the file
  was written badly — fix the file, don't answer in chat, or the next agent hits the same wall.
- Update `status` in the frontmatter when you start and when you finish.

## Format

Copy [_TEMPLATE.md](_TEMPLATE.md). Filename: `T-NN-<kebab-slug>.md`. The five body sections are
not decorative — each one prevents a specific failure:

| Section | Prevents |
|---|---|
| **BACKGROUND** | The agent solving the wrong problem, or "fixing" something that is deliberate |
| **READ FIRST** | Invented API signatures. Exact paths, never "the relevant files" |
| **TASK 1..N** | Scope drift, and a third invented option where a decision was already made |
| **PROHIBITIONS** | The shortcut that makes tests pass while defeating the point of the task |
| **DONE WHEN** | "Works well" as an acceptance criterion. Commands and expected results only |

`PROHIBITIONS` is the section that earns its keep. Name the shortcut that could make tests pass
while defeating the product or safety goal — for example, widening a keyword list to hide a
retrieval failure, weakening the validator, or persisting content for easier debugging.

## Generating a task

In Claude Code, `/task <one paragraph describing what you want>` drafts a file in this format —
it reads the code to fill in `READ FIRST`, measures the current `pytest` baseline, and derives
the standing prohibitions from the repo's privacy invariants. Review the draft before handing it
to an executor; the generator can be wrong about scope in a way the executor will not question.

## Related

- [IMPROVEMENT_BACKLOG.md](../IMPROVEMENT_BACKLOG.md) — historical summary of T-01…T-07.
- [ROADMAP.md](../ROADMAP.md) — the only active order of work.
- [VERIFY_VALIDATION.md](../VERIFY_VALIDATION.md) — the gate that must pass before the first
  Avvalo Verify implementation task is written.
- Founder-owned research or validation may use `owner: founder`; an agent may prepare materials
  but must never fabricate results.
