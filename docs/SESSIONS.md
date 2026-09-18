# Saving your work and resuming in a new window

Nothing carries over between Claude windows except the repo and Claude's memory notes. This page says what is saved
automatically, what is not, and how to pick the project up again from a new window or a new machine.

## What is saved, and where
| What | Where | How |
|---|---|---|
| Code, docs, plans, decisions, the staging artifact | git commits on branch `valuation-phase-2a` | You or Claude commit; restore tags mark milestones (`artifact-main-1`, `staging-vN-YYYY-MM-DD`) |
| Uncommitted and untracked work | `refs/autosave/<branch>` (a local snapshot) | **Automatic** after every response and at session end (`.claude/hooks/autosave.sh`) |
| Claude's memory notes (your preferences, gotchas) | `~/.claude/projects/<project>/memory/`, copied into every snapshot as `.claude/memory-backup/` | Automatic, same hook |
| Your saved properties (Saved tab) | the artifact's platform database | Automatic, syncs across devices; backup box on the Saved tab |
| API keys, the database, the virtual environment | this machine only (git-ignored on purpose) | Never copied anywhere |

The autosave never changes your branch, staging area or files, refuses to snapshot anything that looks like a secret, and
writes a log at `.claude/state/autosave.log`.

## GitHub
Pushing to GitHub is **off by default** (`.claude/autosave.json`, `"push": false`). The GitHub repo was **public** on
2026-09-18, and `docs/artifact/staging.html` embeds a RentCast listings snapshot and FRED/Freddie Mac figures whose terms
say personal use. Decide first: make the repo private (recommended), or strip the embedded data. Then set `"push": true`
and the hook will push the autosave branch, your working branch (never main) and new tags in the background.
Until then, everything is safe on this machine only, so back the folder up (for example Time Machine).

## Starting a new window
1. Open the project folder `/Users/bobjoe/Desktop/nyc-screener` (not a worktree, unless you meant to).
2. A short "Health" line at session start appears only if something needs attention: uncommitted files, commits not on
   GitHub, failing tests or sources, or an autosave problem.
3. Tell Claude: "Read CLAUDE.md, then docs/NEXT.md, and continue." `CLAUDE.md` already tells it to read `NEXT.md` first.
4. Ask for phase status with `cd backend && uv run python -m app.cli status`; never trust a summary.

## Getting work back
- **Recent uncommitted work:** `git diff HEAD refs/autosave/<branch> --stat` shows it. `git checkout refs/autosave/<branch> -- <path>`
  restores a file; `git branch rescue refs/autosave/<branch>` keeps the whole snapshot as a branch.
- **A milestone:** `git checkout <tag>` (for example `staging-v11-2026-09-18`) to look; `git tag` lists them.
- **Memory notes on a new machine:** copy `.claude/memory-backup/*.md` into
  `~/.claude/projects/-Users-<you>-Desktop-nyc-screener/memory/` (the folder name is the project path with `/` replaced by `-`).
- **Saved properties:** they live in the artifact, not in git. Use the Saved tab's backup box to keep a copy.

## Habits that keep this reliable
- End a session by asking Claude to update `docs/NEXT.md` (and `docs/DECISIONS.md` for anything that changes the plan)
  and commit. The autosave is a safety net, not a substitute for a clean commit.
- Never `git add` a whole folder such as `scripts/`: explicit paths only (an undecided folder, `scripts/valuation-spike/`, gets swept in).
- Never move a restore tag with `git tag -f`.
