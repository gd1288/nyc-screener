# FHFA House Price Index (HPI)

**Date:** 2026-10-29 · **Candidate JSON:** `research/candidates/fhfa-house-price-index.json` ·
**Recommendation: recommend-deferred**

## What it is
FHFA's repeat-sales House Price Index. National/state/MSA products are quarterly back to
~1975; county/ZIP/tract products exist too but are annual and (per secondary sources) shorter.
Free CSV/JSON/XML/SQL bulk downloads, no key found for the official downloads. **Caveat:** this
session's network policy blocks `www.fhfa.gov` directly, so this evaluation relies on search-result
summaries and an ALFRED (FRED's sibling) mirror rather than a first-hand read of FHFA's own
page — worth a direct re-check before implementing.

## Why it could help
Two uses: (1) `research-sources/SKILL.md` itself names "FHFA tract HPI growth" as the intended
backtest benchmark for `app/research/evaluate_series.py` (Phase 4, not yet built) — i.e. FHFA's
role may end up being "ground truth to score other candidates against" rather than "metric
exposed in the UI." (2) As a national momentum/valuation series for metros that have neither
NYC's DOF repeat-sales feed nor good Zillow ZHVI coverage.

## Evaluation
- **Granularity:** mixed — quarterly at national/state/MSA, annual and coarser at
  county/ZIP/tract.
- **Cost / license:** free per all sources found; standard government open-data terms.
- No quantitative correlation run — FHFA is itself the proposed *benchmark* for correlation
  testing other candidates, so testing FHFA against FHFA isn't meaningful.

## Recommendation
**Recommend, but deferred.** For NYC today it adds nothing: DOF repeat-sales data is more
granular and NYC-specific, and Zillow ZHVI already covers all 5 boroughs at ZIP level monthly —
FHFA's own NYC-area products are coarser (MSA/county, often annual) than what's already live.
The real payoff is twofold and both are future-dated: (a) a nationally available price series for
metros with no DOF-equivalent sales feed, needed only once the area-model migration happens, and
(b) the formal backtest benchmark once `evaluate_series.py` exists. Don't implement now — revisit
at either of those milestones rather than carrying a second price series with no near-term
beneficiary ahead of the three sources that add genuinely new coverage today.
