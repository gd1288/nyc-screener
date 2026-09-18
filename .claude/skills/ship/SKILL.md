---
name: ship
description: Run the full pre-PR checklist and open a pull request for the current branch's changes. Only invoked explicitly via /ship — never triggered automatically, since opening a PR is a user-facing action that always needs an explicit go-ahead.
disable-model-invocation: true
---

# /ship

Run these steps **in order**, stopping and reporting if any step fails rather than continuing past
a red check. Do not skip a step because "it's probably fine."

## 1. Local checks
```
cd backend && uv run ruff check . && uv run pytest -q
cd frontend && npx tsc --noEmit && npm run lint && npm run build
```
If frontend E2E specs exist (`npm run test:e2e`), run those too. Any failure: stop here, fix or
report — don't proceed to review/commit with red checks.

## 2. Code review
Run `/code-review` against the diff on this branch. Address anything it flags as a real issue
(not style nitpicks it labels as such) before continuing. If it flags something you disagree with,
say why in your report rather than silently overriding it.

## 3. Valuation eval, if touched
If the diff touches `backend/app/valuation/` or `backend/app/scoring/`, run the `valuation-eval-gate`
skill against this diff. A real regression blocks shipping — go fix it, don't ship a worse model and
note it for later; that skill also knows when to pull in the `valuation-reviewer` subagent for a
correctness read. (Before Phase 2a lands, this step will just report there's no eval gate yet —
that's expected, not a failure.)

## 4. Commit
Stage only the files relevant to this change (never a blanket `git add -A`). Write a commit
message explaining *why*, matching this repo's existing commit style (`git log --oneline -10` for
reference). Never commit `.env`, anything under `backend/data/`, or a lockfile hand-edit.

## 5. Push and open the PR
```
git push -u origin <branch>
gh pr create --title "..." --body "..."
```
The PR body should include: a summary of the change, which of the checks above were run and
passed, and a test plan a reviewer can follow. Link the issue this closes if there is one
(`Closes #N`).

## 6. Report
Give the user the PR URL and a one-paragraph summary of what shipped and what was verified. If CI
is configured, note that it's running and where to check it (`gh pr checks`).
