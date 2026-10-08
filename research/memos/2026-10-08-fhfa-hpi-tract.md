# FHFA House Price Index — tract and county/MSA levels

**Candidate file:** `research/candidates/fhfa-hpi-tract.json`
**Recommendation: recommend**

## What it is
FHFA's repeat-sales/repeat-transactions House Price Index, published at several geographies:
- the standard quarterly county/MSA "All-Transactions" index (decades of history, most areas), and
- an annual tract-level "Developmental Index" (`hpi_at_bdl_tract.csv`), built with the same
  repeat-transactions methodology, pinned to 2020 Census tract boundaries, explicitly labeled
  experimental by FHFA.

All downloadable in bulk (CSV/JSON/XML/SQL) from `fhfa.gov/data/hpi/datasets`, no login, no key.

## Why it could help
Two things, really:

1. **It's the backtest yardstick the research-sources skill itself names.** Step 4 of
   `.claude/skills/research-sources/SKILL.md` says to evaluate new candidates by correlating them
   against "FHFA tract HPI growth and Zillow ZORI" — but we don't have FHFA HPI loaded as our own
   data at all right now. Without it, that evaluation step can't actually run for *any* future
   candidate. Loading it is somewhat foundational, not just "one more metric."
2. **It's the cleanest national analog to what the momentum pillar already uses.**
   `neighborhood.py`'s `momentum` pillar leans on `zhvi_cagr_5y/10y` (Zillow) and
   `condo_repeat_sales_cagr` (NYC DOF) — both effectively NYC/Zillow-coverage-area only. CLAUDE.md
   states the project's goal is "generalizing to any US neighborhood," and FHFA HPI is available
   for every US county/MSA and (experimentally) down to the tract level, which Zillow research data
   and NYC DOF sales are not.

## Access, cost, license
Free, no key, no login. Produced by FHFA staff as a U.S. Government Work — public-domain by
default; no explicit restrictive license or ToS turned up in this pass, though it's worth FHFA's
own terms page getting a final glance before shipping.

## Caveats
- The tract-level product is explicitly experimental/developmental and annual, not quarterly — and
  sparse-transaction tracts may simply be missing. Treat the county/MSA "All-Transactions" index as
  the dependable backbone for any new-neighborhood/new-metro expansion, and the tract file as a
  bonus layer where it exists.
- Evaluating this candidate *against* FHFA HPI (the skill's step 4) isn't meaningful since it would
  be the benchmark itself. Its case rests on coverage/methodology fit, not a correlation number.

## Recommendation
Recommend, and treat it as a prerequisite for evaluating other national candidates quantitatively,
not just one more metric in the queue.
