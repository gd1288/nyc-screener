---
name: research-sources
description: Research new free data sources that could improve neighborhood/property valuation (rent growth, vacancy, interest rates, or any other factor an investor cares about). Use when the user asks to look for new data sources, find better predictors, or fill a coverage gap — never runs automatically; every candidate needs the user's approval before it's implemented. Delegates the search to the research-analyst subagent in a forked context.
context: fork
agent: research-analyst
background: false
---

# /research-sources

Hand the stated gap to the `research-analyst` subagent exactly as given — its own procedure
(`.claude/agents/research-analyst.md`) covers the search/evaluate/write-up steps, hard caps, and
stop condition. Don't pre-filter or narrow candidates yourself first; that's its job.

If the user didn't state a specific gap (bare "find new data sources" with nothing else), ask what
they want researched (a specific factor, a coverage hole, "whatever `research/gaps.json` says is
missing" once that exists) rather than letting the subagent guess scope on its own.

Report back the subagent's findings — the ranked candidates and memo paths, or a plain negative
result if nothing cleared the bar — don't just relay "done." Never implement anything from this
skill: that only happens after the user approves a specific candidate, in a normal (non-forked)
session, via `add-data-source`.
