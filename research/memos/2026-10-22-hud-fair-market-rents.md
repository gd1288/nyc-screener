# HUD Fair Market Rents (FMR / Small Area FMR)

**Recommendation: do not recommend**

## What it is
HUD's annual benchmark rent figures by bedroom count, used to set Section 8 voucher payment
standards. Standard FMRs are county/metro level; Small Area FMRs (SAFMRs) go down to 5-digit ZIP
in many metros, including NYC. Free via the official HUD USER API with a free registration token
(one-screen signup).

## Why I looked at it
Rent data feeds directly into `backend/app/scoring/investment.py`'s cap-rate and cash-flow math,
so a free, national, government rent benchmark looked promising on paper.

## Evaluation
- **What's already there**: `backend/app/sources/zillow_research.py` covers rent trend data
  (ZORI), and `rentcast.py` pulls actual asking-rent listings (budget-capped at 31 requests/month,
  enforced by that adapter). Between the two, the project already has both a trend series and
  real market observations.
- **The specific problem with FMR as a rent estimate**: it's a voucher-program administrative
  benchmark, not a market-rate observation, and it's well documented that FMR runs below true
  market rent in strong/gentrifying submarkets — precisely the neighborhoods this screener is
  built to flag. Using it as a primary or fallback rent number risks systematically understating
  cash flow exactly where the tool is supposed to be most useful.
- **History**: annual point-in-time files, not a continuous series — weak for any kind of
  backtest even if the bias problem weren't there.
- **Cost/license**: free, government data, token signup only extra friction.

## Recommendation
Do not recommend as currently scoped. The gap it would fill (a rent number) is already covered,
and its administrative basis makes it a biased estimator for the specific use case. A narrower
version of this — FMR as a last-resort rent floor only in neighborhoods with zero RentCast/ZORI
coverage — is a thin, speculative use case that doesn't justify the adapter and auth-token setup
right now. Revisit only if a real "no rent data at all for this neighborhood" gap shows up in
practice.
