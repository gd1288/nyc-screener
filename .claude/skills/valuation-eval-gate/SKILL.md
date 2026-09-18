---
name: valuation-eval-gate
description: Check the valuation engine and neighborhood-scoring backtest haven't regressed before merging a change to backend/app/valuation/ or backend/app/scoring/, once Phase 2a's eval.py exists. Use for "check the valuation eval", "did this regress the backtest", or as a pre-merge gate on valuation/scoring changes.
---

# valuation-eval-gate — regression check for valuation and scoring

**Precondition**: this skill assumes Phase 2a of the approved workflow plan has landed —
`backend/app/valuation/eval.py` (median abs % error vs. a stored baseline) and Phase 1's
generalized backtest. As of creation (2026-09-17), `backend/app/valuation/` doesn't exist yet.
**Step 0 checks this for real** every time — see Guardrails.

## 1. Name
`valuation-eval-gate`.

## 2. Description
Fires on "check the valuation eval", "did this regress the backtest", "is this safe to merge", or
is called from `ship` (see the improvement made to that skill alongside this one) whenever a diff
touches `backend/app/valuation/` or `backend/app/scoring/`.

## 3. Body / instructions
0. **Check the precondition**: `test -f backend/app/valuation/eval.py`. If missing, report that
   Phase 2a hasn't landed and there's no eval gate to run yet — stop there. If the diff being
   checked only touches `backend/app/scoring/` and Phase 2a hasn't landed, fall back to running
   just `backend/app/scoring/backtest.py`'s existing check (whatever form it takes today) rather
   than reporting nothing.
1. **Run the eval**: `cd backend && uv run python -m app.valuation.eval` (or whatever its actual
   invocation turns out to be — re-derive from the real file once it exists, this is a sketch).
   Compare the reported median absolute % error against the stored baseline
   (`research/evals/baseline.json` per the plan).
2. **Run the generalized backtest** across every watched region (not just NYC) and note any region
   whose predictive correlation dropped noticeably, not just the aggregate.
3. **Decide, don't just dump numbers**: if nothing regressed, say so plainly and briefly. If
   something did, that's a genuine judgment call (is it noise, a real bug, or an expected tradeoff
   the user already knew about?) — this is exactly the point of a skill rather than a bare script.
4. **On a real regression**, hand off to the **`valuation-reviewer`** subagent for a correctness
   read on the diff, rather than trying to diagnose the math yourself — that subagent's whole job
   is this.
5. **Never update the stored baseline yourself.** A baseline update is a deliberate decision that
   the new numbers are the new normal — that's the user's call (see Guardrails).

Expected output: a pass/fail-with-numbers report, and — only on a real regression — a clear
statement of what changed and a request to either fix it or explicitly accept the new baseline.

## 4. Gotchas
- *(none yet — no real run against live Phase 2a code. Add a dated entry the first time this
  actually runs against a genuine regression or false positive.)*

## 5. Guardrails
- **Step 0 is not optional** — check the actual file exists before assuming the eval script's
  interface matches this document's sketch.
- **Never edit `research/evals/baseline.json`** (or wherever the baseline actually lands) from
  inside this skill — accepting a new baseline is the user's decision, not an automatic outcome of
  a passing review.
- Read-only against the valuation/scoring code itself — this skill reports, it doesn't fix; a fix
  is a separate, explicit ask (possibly to `/debug` or a direct edit).
- Never run against `backend/data/screener.db` directly with an unbounded query — any SQL this
  skill runs must have a `LIMIT`, per root `CLAUDE.md`'s hard rules, same as any other tool call
  against that database.

## 6. Embedded skills and callouts
- **`valuation-reviewer`** subagent (`.claude/agents/valuation-reviewer.md`) — the correctness-read
  step on an actual regression; this skill runs the checks and makes the call on whether to
  escalate, not the deep math review itself.
- **`ship`** — calls this skill conditionally; see that skill's updated checklist.
- **`add-region`** — a different report (neighborhood-level backtest for one new region), not this
  skill's job (valuation-engine + all-region backtest regression).

## 7. Memory allocation
The baseline file itself (once it exists) is the only durable state this check depends on, and it
lives in the repo under `research/evals/` per the plan — not duplicated anywhere by this skill.

## 8. Frontmatter controls
Only `name` and `description`. No `context: fork` — regression numbers need to reach the main
conversation directly since they may change what the user does next. No `agent:` (it *calls*
`valuation-reviewer` when warranted, rather than being that agent). Not `background:`.

## 9. Sub-files, scripts and evals
- **Structural check**: shared linter —
  `python3 .claude/skills/tony-stark/scripts/structural_check.py .claude/skills/valuation-eval-gate/SKILL.md`.
- **Live run**: at creation time, the only real thing to invoke is step 0's precondition check —
  see [CHANGELOG.md](CHANGELOG.md) for its actual (negative) result. Re-run for real once Phase 2a
  exists and log what actually happened.

## 10. Versioning and iteration
Logged in [CHANGELOG.md](CHANGELOG.md). Expect real edits once Phase 2a's actual `eval.py`
interface is known.
