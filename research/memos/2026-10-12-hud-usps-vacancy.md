# HUD Aggregated USPS Administrative Data on Address Vacancies

**Date:** 2026-10-12 · **Verdict:** Reject · **Gap:** US-wide, tract-level vacancy signal to
generalize the demographics/momentum pillars beyond NYC-specific sources.

## What it is
HUD tabulates USPS address-management data (vacant residential/business/other addresses) by census
tract, nationally, quarterly. This would have been an excellent granularity match for this
project -- census tract, matching the project's existing tract-to-NTA aggregation pattern used by
`census_acs.py`.

- **URL:** https://www.huduser.gov/apps/public/usps/home
- **Granularity:** census tract.
- **Update frequency:** quarterly.
- **History:** HUD's own FAQ flags a known discontinuity from USPS's "Move to Competitive"
  delivery-point program that complicates longitudinal comparisons. The commonly-cited 2005-2006
  start date is from general knowledge, not confirmed by a source this run -- moot anyway since
  access is disqualifying regardless of history length.

## Why it was rejected
Access is gated: HUD's sublicense agreement with USPS restricts this dataset to **registered
government entities and non-profit organizations only**, for the stated purpose in that sublicense
agreement. This project does not qualify for registration at all -- this isn't a "sign up for a
free key" gate like FRED or Census, it's an eligibility gate this project fails outright, on top of
requiring a login. That fails step 3 of `.claude/skills/research-sources/SKILL.md` ("no login wall,
no clause blocking commercial/product use"), so this was rejected on access grounds without reaching
a cost/license/correlation evaluation.

## Evaluation
Not run -- disqualified on access before any further evaluation was attempted.

## Recommendation
**Reject, but worth recording why rather than silently dropping it.** Of everything evaluated this
run, this was genuinely the best-fitting granularity (tract, quarterly, long history) for the
stated gap. The only disqualifying factor is eligibility, not data quality. Re-check only if the
project's organizational status changes (e.g. a university or non-profit research affiliation) or
if HUD's sublicense terms with USPS change -- don't re-propose this on the same facts.
