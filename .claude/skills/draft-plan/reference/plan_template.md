# Plan file template

Every `plans/issue-<N>.md` follows this shape. Keep it short enough to actually get read before
implementation starts — this is a working plan, not a spec document.

```markdown
# Plan: issue #<N> — <short title>

## Problem
What's actually broken or missing, in 1-3 sentences. Link the issue.

## Approach
The chosen approach, and — only if it's non-obvious — the one-line reason an alternative was
rejected. Don't list every option considered; state the one being taken.

## Files
Every file expected to change or be added, each with a one-line reason. If a file is uncertain
until investigation starts, say so rather than guessing a full list.

## Steps
Ordered, concrete steps. Each step should be small enough to check off, not "implement the
feature" as one line.

## Tests
What gets added or run to confirm this works — specific commands (`uv run pytest ...`,
`npx tsc --noEmit`), not "add tests."

## Risks
What could go wrong or take longer than expected. Skip this section only if there's genuinely
nothing worth flagging — don't pad it.

## /goal
One line: the checkable pass condition plus a turn-count stop clause, e.g.
`uv run pytest exits 0, ruff check is clean, only the files listed above changed — or stop after 30 turns`.
```
