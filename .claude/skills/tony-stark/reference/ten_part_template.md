# Ten-part skill template

Copy this into a new `SKILL.md`, fill every section, and keep the numbering and headings verbatim
(`scripts/structural_check.py` matches on them). If a section genuinely doesn't apply, replace its
body with a single line: `N/A — <concrete reason>`. Don't delete a heading to skip it.

Frontmatter goes above the `# Title` line:

```
---
name: <folder-name, must match this value exactly>
description: <when this is useful, in the words the person will actually say; keep it specific and under 1024 characters>
---
```

---

## 1. Name
The stable name for this workflow. State it, and confirm the folder is named the same.

## 2. Description
When is this useful? Use the actual phrases someone would type to trigger it. Keep the scope
specific enough that it doesn't fire on unrelated requests.

## 3. Body / instructions
The repeatable method, as ordered steps. For each step that needs one, state:
- the required input(s),
- what "done" looks like for that step,
- what to do if an input is missing (usually: stop and ask, don't invent).

End with what the finished output is and how the user checks it's correct.

## 4. Gotchas
Traps actually hit in real runs, each with enough detail to recognize it again. Format:
`*(YYYY-MM-DD: what happened, and what to do differently.)*`. Don't pre-fill this with
hypothetical failure modes — leave it short at creation time and let real runs fill it in.

## 5. Guardrails
- What this skill is permitted to do on its own.
- What it must stop and get a yes for first (anything that sends, publishes, spends, deletes,
  installs, or overwrites).
- What to do when a required input is missing or ambiguous (default: stop and ask — never
  invent a business fact like an owner, threshold, or account).

## 6. Embedded skills and callouts
Other skills, scripts, or reference files this one leans on, each with its path and *why* — not
just a list of names. If another skill covers overlapping ground, say so explicitly and state the
boundary (what stays here vs. what defers to it).

## 7. Memory allocation
What must stay in this file for the method to work, versus what's offloaded to a sub-file and
loaded only when needed. State where any state this skill produces or approves actually lives
(a file in the repo, a specific external system) — don't leave it implicit.

## 8. Frontmatter controls
List the frontmatter fields actually set and why each is needed for the target platform. Explicitly
note any field considered and deliberately left out.

## 9. Sub-files, scripts and evals
For this workshop convention: exactly one structural/deterministic check (what it verifies, how to
run it) and one realistic live run (what makes it realistic, and where its safe to run — a scratch
workspace, not production data or a real send/publish/spend/delete).

## 10. Versioning and iteration
Where changes to this skill get logged (a `CHANGELOG.md` alongside it is the default), and the
rule that a previous working version stays recoverable (git history is the default mechanism —
don't hand-roll `.bak` files or `_v2` folders unless the target platform has no version control).
