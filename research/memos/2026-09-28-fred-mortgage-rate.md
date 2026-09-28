# FRED 30-Year Fixed Rate Mortgage Average (MORTGAGE30US)

**Recommendation: recommend-with-caveats**

## What it is
A weekly national average 30-year fixed mortgage rate, sourced from Freddie Mac's Primary
Mortgage Market Survey and republished by FRED (Federal Reserve Bank of St. Louis). Free API,
requires a no-cost registered key (same shape as the `census_api_key` this project already
handles). History runs back to April 1971, weekly cadence, no seasonal-adjustment caveats.

## Why it could help
`backend/app/scoring/investment.py` defines:
```python
interest_rate: float = 0.065
```
as a hardcoded default on the `Assumptions` dataclass used for every IRR/cash-flow projection in
the investment scoring engine. There is no data source anywhere in `app/sources/` or
`sources.yaml` that feeds this -- it's a constant someone will need to remember to update by hand
as rates move, and every projection silently uses last-edited-by-hand until they do. A weekly FRED
pull would let the default track reality, and let the assumptions UI show "current 30yr rate: X%
(as of <date>)" instead of a bare editable number.

It's also a strong fit for `backend/CLAUDE.md`'s stated (not-yet-built) valuation invariant:
> Every `FactorDef.market_estimate()` must return its P10/P90 range, source, and as-of date -- the
> UI shows these, and Monte Carlo sampling needs the range.

50+ years of weekly history gives plenty of room to compute trailing P10/P90 bands (1yr/5yr/10yr
windows) for exactly that kind of Monte Carlo input, once `app/valuation/` exists.

## Evaluation
- **Cost**: free. Requires free email-registered API key (or see below).
- **License: UNVERIFIED for commercial/product use -- review before implementing.** FRED's own
  terms explicitly cover non-commercial, educational and personal use, and say commercial use
  carries "additional restrictions" without spelling out what those are for this series.
  `fred.stlouisfed.org` was egress-blocked from this research environment, so its terms-of-use
  page could not be read directly this run -- only surfaced via search snippets. Checked the
  original source as a cross-check: Freddie Mac publishes PMMS data itself at
  `freddiemac.com/pmms`, copyrighted, "may be used with proper attribution" (no alteration, no
  warranty) -- suggestive that attributed use is fine, but not an explicit commercial-use grant
  either, and that page also appears to need no API key, which would sidestep the FRED
  registration entirely. Read both terms pages directly before implementing; this is the one open
  question keeping this at "recommend-with-caveats" rather than a flat recommend.
- **Granularity**: national -- a single scalar series, not per-neighborhood.
- **History**: 55 years, weekly. More than sufficient.
- **Correlation**: not computed. `app/research/evaluate_series.py` (referenced by the
  research-sources skill as "Phase 4") does not exist yet in this repo, so no quantitative
  lead/lag or correlation check against FHFA HPI / ZORI was possible this run. The economic
  linkage (affordability -> demand -> appreciation) is well established in general but not
  measured here -- flagging this honestly rather than asserting a number.

## Architecture note (for whoever implements this)
This does not fit any of the five existing `Source.kind` values (`boundaries`, `neighborhood`,
`sales`, `listings`, `sold_check`) -- those all key off a per-neighborhood or per-property
identity, and this is one national number. Two reasonable paths:
1. A small new `MacroSeries`-style table + a new source kind, feeding `Assumptions.interest_rate`
   directly.
2. Fold it into `app/valuation/engine.py`'s planned `FactorDef.market_estimate()` once that module
   exists, which already wants exactly this shape (P10/P90 range + source + as-of date).

Recommend (2) if the valuation engine work is imminent, since it avoids building throwaway
infrastructure; (1) if the investment-scoring fix is wanted sooner than that.

## Bottom line
Concrete, verified gap (a hardcoded constant with real analytical consequences), free government
(or Freddie Mac direct) source, no NYC-specific dependency (fits the project's
generalize-to-any-US-market goal trivially, since it's national). Two open items before
implementation: confirm commercial-use licensing terms directly (see above), and decide the (a)
new-table vs (b) valuation-engine schema question -- neither is a reason to reject the candidate,
but both should be resolved before an `add-data-source` task starts, not during it.
