# FRED 30-Year Fixed Rate Mortgage Average (MORTGAGE30US) — RECOMMEND

**What it is:** Freddie Mac's Primary Mortgage Market Survey weekly average 30-year fixed
mortgage rate, published via the Federal Reserve Bank of St. Louis's FRED. National series, back
to April 1971.

**Why it could help:** `app/scoring/investment.py`'s `Assumptions.interest_rate` defaults to a
hardcoded `0.065` for every projection, no matter when the screener is actually run. Over just the
last two years, 30-year rates have moved across roughly a 6-8% range — enough to materially change
every projected IRR, monthly payment, and cash-on-cash return the investment math produces. Feeding
in the live/current rate instead of a stale constant would make those numbers reflect the market the
user is actually screening in.

**Evaluation:**
- Access: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US` is documented (by
  FRED's own graph-download help pages and third-party code using this exact URL pattern) to return
  a plain CSV with no API key — the same no-login, direct-CSV shape `zillow_research.py` already
  uses. (FRED's *registered* API, by contrast, does require a free key — this candidate
  deliberately uses the key-free CSV route instead.) **Not independently verified this run:** a
  direct `curl` to `fred.stlouisfed.org` from this session was rejected by this environment's
  egress proxy (403, "no rule or network setting allows this host") — that's this sandbox's network
  policy, not a finding about the endpoint itself, but it means the claim above rests on
  documentation, not a fetch. Worth a live check once implementation needs the host allowlisted.
- History/cadence: weekly, back to 1971 — far more history than needed.
- License: FRED notes the underlying data is Freddie Mac's and should be attributed, not resold as
  a dataset; reading a single current value into an internal calculation and citing Freddie
  Mac/FRED if ever surfaced in the UI is consistent with that.
- Quantitative correlation: not applicable — this is a financing-cost input to the investment math,
  not a predictor being tested against appreciation, so `evaluate_series.py`-style correlation
  testing doesn't apply here the way it would for a neighborhood growth signal.

**Implementation note:** this is a single national scalar, not a per-neighborhood metric, so it
doesn't fit the existing `kind: neighborhood` / `write_metrics` `Source` contract cleanly. It would
need a small new home — e.g. a one-row assumptions/settings table, or a new `kind: macro` on
`Source` — rather than being shoehorned into `NeighborhoodMetric`. That's a real design decision for
whoever implements it, not a reason to reject the source itself.

**Recommendation: recommend.** Directly fixes a known hardcoded assumption with a free,
no-key, well-established government-adjacent series; the only cost is a small architectural
decision about where a single national value lives.
