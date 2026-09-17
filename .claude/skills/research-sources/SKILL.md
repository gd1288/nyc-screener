---
name: research-sources
description: Research new free data sources that could improve neighborhood/property valuation (rent growth, vacancy, interest rates, or any other factor an investor cares about). Use when the user asks to look for new data sources, find better predictors, or fill a coverage gap — never runs automatically; every candidate needs the user's approval before it's implemented.
context: fork
---

# Researching new data sources

You act as a research analyst proposing candidates, not an implementer. **Never write an adapter,
edit `sources.yaml`, or touch `app/sources/` from this skill** — that only happens after the user
approves a specific candidate, at which point the `add-data-source` skill handles it in a normal
(non-forked) session. This skill's whole job is: search, evaluate, write up, stop.

## Hard caps (this is a budget-bounded search, not open-ended browsing)
- At most **8 web searches**.
- At most **5 candidates** carried through to evaluation.
- If `research/registry.json` exists, skip anything already there (approved or rejected within the
  last 90 days) — read it first so you don't re-propose something already declined.

## Procedure
1. **Read the gap.** Check `research/gaps.json` if it exists (from `app.cli research-gaps`, once
   built); otherwise take the user's stated gap directly (e.g. "rent growth predictors",
   "vacancy rate data", "a better mortgage-rate series").
2. **Search** (≤8 queries): prioritize free, no-login, documented APIs or bulk downloads over
   scraped or paid sources. Government (Census, BLS, FRED, HUD, FHFA, EPA, FEMA) and established
   open-data portals (Socrata city/state portals) are strongly preferred over a random blog's CSV.
3. **Narrow to ≤5 candidates**, and for each record:
   - What it measures, update frequency, and geographic granularity (tract/ZCTA/county/national —
     national is preferred per this project's US-wide goal; NYC-only is acceptable only for a
     clearly NYC-specific signal).
   - Cost: confirm actually free (not a trial), and any rate limit.
   - License/ToS: no login wall, no clause blocking commercial/product use.
   - History available (need enough backdated history for the backtest to mean anything — a
     series that only started last year is weak evidence).
4. **Evaluate quantitatively, not just qualitatively.** If `app/research/evaluate_series.py`
   exists (Phase 4), run it: correlation and lead/lag of the candidate series against FHFA tract
   HPI growth and Zillow ZORI, across more than one region if possible. A candidate that "sounds
   useful" but shows no measurable correlation or lead time is a weak proposal — say so plainly
   rather than talking it up.
5. **Write the candidate JSON** to `research/candidates/<slug>.json` following
   `research/candidates/schema.json` (create the schema file on first use if it doesn't exist yet:
   name, url, coverage, granularity, update_frequency, license, cost, correlation results if
   computed, and a one-paragraph recommendation).
6. **Write a one-page memo** to `research/memos/<date>-<slug>.md`: what it is, why it could help,
   the evaluation numbers, and an explicit recommend/don't-recommend.

## Stop condition
Stop after the 5th candidate or the 8th search, whichever comes first, even if you haven't found
something great — a thorough negative result ("searched N sources, none cleared the bar because
X") is a valid and useful output, not a failure to fix by searching more.

## Reporting
Present the candidates plainly, ranked by your recommendation, with the memo paths. Do not
implement anything. The user (or a Workbench "Approve" action, once built) decides which candidate
becomes a real `add-data-source` task.
