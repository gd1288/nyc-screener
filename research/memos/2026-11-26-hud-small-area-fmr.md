# HUD Small Area Fair Market Rents (SAFMR) — RECOMMEND

**What it is:** HUD's annually-published, federally computed rent-by-bedroom-count figure. ZIP-level
("small area") in ~40 designated metro areas including NYC; county/CBSA-level everywhere else.
Used nationwide to set Section 8 Housing Choice Voucher payment standards, so it's built to be
methodologically consistent across very different markets.

**Why it could help:** the project's only rent series today is Zillow Research ZORI
(`zillow_research.py`), which is a strong, high-frequency series but — like most Zillow Research
data — has patchy or missing coverage once you leave large metro ZIPs. That cuts against this
project's explicit "generalizing to any US neighborhood" goal. SAFMR gives a federal, standardized
rent figure for essentially every ZIP in the country (small-area ZIP figure in designated metros,
coarser county/CBSA figure elsewhere), so it's a natural fallback/cross-check where ZORI is thin.

**Evaluation:**
- Granularity: ZIP (ZCTA) in SAFMR-designated metros, county/CBSA elsewhere — comparable to or
  finer than Zillow's ZIP-level ZHVI/ZORI in the areas where both exist. The exact list/count of
  SAFMR-designated metros and the earliest available SAFMR fiscal year were **not confirmed this
  run** — verify both on huduser.gov before implementing.
- Update frequency: annual (new fiscal-year file each October) — coarser than Zillow's monthly
  cadence, so it's a complement, not a replacement.
- Access: HUD's official API needs a free bearer token (registration at huduser.gov, not a login
  wall or paid tier) — the same shape of friction `census_acs.py` already accepts for
  `CENSUS_API_KEY`. Bulk spreadsheet downloads also exist without going through the API at all.
- License: US federal data, public domain.
- **Methodology caveat:** Fair Market Rents are set at roughly the 40th percentile of gross rent
  (rent + utilities) in the area — a deliberately below-median figure, by design, for setting
  voucher payment standards. That means raw FMR numbers will likely read below market asking rent
  for condos specifically, and shouldn't be compared directly against Zillow ZORI without
  accounting for that gap.
- Quantitative correlation: not run this pass. Before trusting SAFMR numbers in areas where Zillow
  has no coverage, it would be worth checking SAFMR vs. ZORI agreement (with the percentile gap
  above in mind) in NYC NTAs where both exist, as a sanity check on methodology differences.

**Recommendation: recommend**, with the caveat that its main value is filling Zillow's coverage
gaps for non-NYC rollout rather than adding a new signal within NYC itself — scope and prioritize
accordingly if the near-term roadmap is still NYC-focused.
