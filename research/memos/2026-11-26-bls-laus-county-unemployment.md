# BLS Local Area Unemployment Statistics (LAUS), county-level — DO NOT RECOMMEND

**What it is:** BLS's monthly county-level employment/unemployment estimates, covering over 7,500
areas nationally. The public v1 API needs no registration (25 series per query, 25 queries/day, up
to 10 years of history per request — easily enough for this project's cadence); v2 unlocks higher
limits with a free key.

**Why it was considered:** employment growth is a plausible leading indicator for housing demand,
and it's free, government-produced, national data — a reasonable fit alongside the project's other
ACS/BLS-style signals.

**Evaluation:**
- Granularity: county is the finest level LAUS publishes. NYC's five counties are its five
  boroughs — this cannot distinguish neighborhoods within a borough at all. Every other signal
  already feeding the Growth Score (housing pipeline, rezonings, subway access, crime, liquor
  licenses, ACS income/education) operates at NTA granularity; a borough-level-only metric would
  functionally be the same number copy-pasted across dozens of NTAs per borough.
- Reliability: at least one recent month's county release was reportedly delayed/canceled during a
  government shutdown (per BLS and state labor-agency notices), and LAUS data gets revised annually
  via benchmarking — manageable, but worth knowing before depending on monthly freshness.
- Cost/access: genuinely free and key-free at the v1 tier, so there's no access-cost reason not to
  use it — the problem is purely granularity.
- Quantitative correlation: not computed this pass.

**Recommendation: do not recommend** as evaluated (county-level). Employment is a reasonable
signal in principle, but this project is actively building out NTA-level granularity and a
county-level number would be a step backward in resolution relative to everything else already in
the Growth Score. County is also the finest geography BLS's own establishment-level program (QCEW)
publishes — it does not reach ZIP level, so QCEW isn't a fix for this granularity problem either.
A genuine sub-county employment proxy would have to come from elsewhere, e.g. Census ZIP Code
Business Patterns (ZBP), which this run's search budget didn't reach. Worth reconsidering paired
with ZBP or another sub-county source in a future pass, not with BLS data alone.
