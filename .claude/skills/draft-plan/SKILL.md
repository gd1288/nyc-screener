---
name: draft-plan
description: Turn a GitHub issue on this repo into a structured plan file before implementing it. Use when the user says "draft a plan for issue N", "plan out issue N", or "what's the plan for #N" — produces plans/issue-N.md with problem/approach/files/steps/tests/risks and a /goal condition, and optionally posts it as an issue comment (only with explicit go-ahead).
---

# draft-plan — issue → structured plan file

## 1. Name
`draft-plan`.

## 2. Description
Fires on "draft a plan for issue N", "plan out issue N", "what's the plan for #N", or the user
pasting an issue number/URL and asking for a plan before implementation starts. This is the
chat-usable version of the Workbench "Plan" tab described in the approved workflow plan
(`/Users/bobjoe/.claude/plans/i-want-to-create-mellow-quill.md`, Phase 2b) — usable now, without
waiting for that UI to exist.

## 3. Body / instructions
1. **Read the issue**: `gh issue view <N> --json title,body,labels,comments`. If `gh` isn't
   authenticated or the issue doesn't exist, stop and say so — don't guess at issue content.
2. **Read enough of the repo to plan accurately**: the relevant `CLAUDE.md` (root, and
   `backend/CLAUDE.md` / `frontend/CLAUDE.md` if the issue touches that side), and the files the
   issue's own description points at. Don't do a full codebase sweep — read what's needed to name
   concrete files and steps.
3. **Draft the plan** using [reference/plan_template.md](reference/plan_template.md): problem
   statement, approach, exact files to touch, ordered steps, tests to add/run, risks, and one
   `/goal` line (a checkable pass condition + a turn-count stop clause, matching the style already
   used in the approved workflow plan's phases).
4. **Write `plans/issue-<N>.md`** at the repo root (create `plans/` if it doesn't exist).
5. **Ask before posting.** Posting the plan as a comment on the GitHub issue is publishing to a
   shared, visible place — always ask first, even though writing the local file needs no
   confirmation. If the user says yes: `gh issue comment <N> --body-file plans/issue-<N>.md`.
6. **Hand off**, don't implement. This skill's job ends at a written, reviewable plan — starting
   the actual implementation is a separate, later action (Plan Mode, or a fresh session against
   the written plan file), not something this skill continues into automatically.

Expected output: `plans/issue-<N>.md` on disk, shown to the user, posted to the issue only if they
said yes.

## 4. Gotchas
- **Don't invent acceptance criteria the issue doesn't state.** If the issue is vague about done
  criteria, ask, or write the plan's `/goal` line as a proposal and flag it as needing the user's
  sign-off rather than presenting it as already agreed.
- **`gh` auth is per-machine, not guaranteed.** A stale token or no `gh auth login` yet shows up as
  a generic-looking error from `gh issue view` — check `gh auth status` if the first call fails
  before assuming the issue number is wrong.
- **Issue numbers aren't the same as PR numbers** on GitHub (they share one counter) — confirm
  `gh issue view <N>` actually returns an issue, not silently resolve a PR with the same number.

## 5. Guardrails
- Writing `plans/issue-<N>.md` locally needs no extra confirmation (it's a plain repo file, not a
  send/publish/spend/delete action).
- **Posting the plan as an issue comment always needs an explicit yes in this conversation** —
  a previous approval for a different issue doesn't carry over.
- Never start implementing the plan from inside this skill — that's a distinct, later step the
  user asks for separately.
- If the issue is missing information the plan genuinely needs (e.g. no acceptance criteria, no
  named files), stop and ask rather than filling it in with a guess.

## 6. Embedded skills and callouts
- [reference/plan_template.md](reference/plan_template.md) — the exact section structure every
  drafted plan follows, kept separate so this file doesn't repeat it.
- The approved workflow plan (`/Users/bobjoe/.claude/plans/i-want-to-create-mellow-quill.md`) —
  read for the `/goal`-line style and phase context when the issue is part of that multi-phase
  effort; not needed for an unrelated one-off issue.
- Complements, doesn't replace, the future Workbench "Plan" tab (Phase 2b) — once that exists it
  wraps the same idea with a UI and a headless runner; this skill stays useful as the
  chat-native path.

## 7. Memory allocation
The plan template lives in its own file (see above) so this core stays short. Approved state is
just the written `plans/issue-<N>.md` file in the repo — git is its version history, same as any
other tracked file. Nothing else needs to persist across sessions for this skill to work.

## 8. Frontmatter controls
Only `name` and `description`. No `context: fork` — the mid-task "ask before posting" checkpoint
needs to happen in the main conversation, which a forked context would complicate. No `agent:` —
no specialized tool subset beyond normal read/`gh`/write. Not `background:` — the user is present
to answer the posting question.

## 9. Sub-files, scripts and evals
- **Structural check**: shared linter —
  `python3 .claude/skills/tony-stark/scripts/structural_check.py .claude/skills/draft-plan/SKILL.md`.
- **Live run**: a real invocation against a real issue in this repo (see
  [CHANGELOG.md](CHANGELOG.md) for what was actually run and what came back) — not a canned
  fixture, since the point is confirming `gh` auth, issue access, and file-writing actually work
  end to end.

## 10. Versioning and iteration
Logged in [CHANGELOG.md](CHANGELOG.md). Previous versions recoverable from git history on this
file.
