# Valuation methodology: what to carry forward from two prior models

**Date:** 2026-09-17
**Status:** Spec for `backend/app/valuation/proforma.py` and `taxes.py`
**Sources reviewed:**
- `421 Harris Simulation Model Investment Analysis.xlsx` — Crystal Ball Monte Carlo model of a
  7-unit rental ($1,681,440 purchase, 10-year hold, 40% down at 4.5%).
- `~/Desktop/Python Projects/real estate.ipynb` + `test real estate val.py` (Dec 2024) — XGBoost
  rental-growth model over 48 US cities feeding base/bull/bear DCFs.

Neither is a reference implementation. Both are mined for methodology. This memo is the design
spec that comes out of that review.

---

## 1. The underwriting chain — adopt wholesale

The workbook's spine is the standard institutional sequence, and its sheet-per-stage layout is a
sound architecture rather than a spreadsheet convention. It becomes the shape of `proforma.py`:

```
Rent roll -> Potential Gross Rent -> vacancy -> other income -> Effective Gross Income
  -> itemized operating expenses -> Net Operating Income
  -> annual debt service -> Before-Tax Cash Flow
  -> depreciation -> taxable income -> income tax -> After-Tax Cash Flow
  -> reversion (exit value, costs, basis, taxes) -> equity reversion
  -> DCF -> IRR / NPV -> ratio and risk block
```

Each stage consumes only the stage above it. That property is what makes the model auditable, what
lets the Excel export mirror it sheet-for-sheet, and what enables the "explain this number"
drill-down in the UI.

---

## 2. Formulas and techniques worth keeping

| Technique | Source cell | Why keep it |
|---|---|---|
| Mortgage balance via `PV(rate, remaining_periods, -payment)` | `Mortgage!D24` | Closed-form remaining balance, no iteration. Equivalent to the existing `loan_balance()` in `app/scoring/investment.py` — mutual confirmation both are right. |
| Interest/principal split by difference | `Mortgage!D20:D21` | `principal[t] = balance[t-1] - balance[t]`; `interest[t] = debt_service - principal[t]`. Avoids a second amortization formula that could drift from the first. |
| Exit value = NOI / cap rate | `Sale!F9`, `J10` | The reversion method. **Refinement:** use forward (year-11) NOI — a buyer prices next year's income, not last year's. |
| A valuation *range* from multiple exit caps | `Sale!J9` (5.0%) vs `J10` (5.5%) | Two cap rates side by side give a range instead of a false point estimate. Maps onto the existing `scenarios.compare`. |
| Adjusted-basis chain | `Sale!F29:F35` | Purchase + transaction costs - cumulative depreciation + selling costs. Correctly nets selling costs against the amount realised. |
| Gain split into recapture vs. capital gain, taxed separately | `Sale!K16:K24` | The two carry different rates; collapsing them into one is a material shortcut. Keep the split. |
| After-tax equity reversion | `Sale!K29:K35` | Price - selling costs - mortgage balance - taxes on sale. |
| Mid-month convention | `ATCF!R9` (`x 11.5/12`) | Correct first/last-year depreciation proration. Easy to forget. |
| Management fee as % of EGI, not gross rent | `Expenses!L7` -> `K22` | Subtle and correct: you cannot manage income you never collect. |
| Separate growth rate for property taxes | `Expenses!F10` vs `F7` | Taxes and operating costs escalate differently, especially in NYC. |
| Per-unit expense scaling | `Expenses!R6:R9` | Turnover, landscaping, repairs and reserves scale with unit count, not revenue. |
| Operating expense ratio tracked per year | `Operating!C33:U33` | OpEx / EGI over time reveals margin compression a single-year view hides. |
| Break-even ratio | `Ratio2!J12` | `(OpEx + ADS) / EGI` — the occupancy needed to cover everything. One of the most useful risk numbers in the workbook. |
| DCR, LTV, cap rate, equity dividend rate (pre- and post-tax) | `Ratio2` | The standard lender/investor ratio block. |
| GRM / GIM / NIM used **both** ways | `Ratio1` | Computed from price to benchmark a deal, and inverted (`Value = NOI x NIM`) as an independent valuation method. The second use is the valuable one. |
| Payback period with fractional interpolation | `Risk!E18` | `year + cumulative / next year's flow` — a real figure rather than a rounded year count. |
| Comparable-sales grid building the purchase price | `Intro!Q5:W8` | Unit counts x per-unit comp prices with an adjustment factor: a sales-comparison approach sitting beside the income approach. |
| Holding-period gating throughout | `IF(Intro!$E$10 > n, ...)` | One input drives the length of every schedule. |

---

## 3. Ideas worth carrying from the Python prototype

1. **Growth predicted from area economic factors** rather than assumed. The most valuable idea in
   either file. The prototype's factor list — median income, unemployment, population growth,
   inflation, housing supply, interest rate, crime, education quality, transit access, historical
   growth, historical vacancy — is almost exactly what this project already collects as real
   `neighborhood_metrics` behind the Growth Score. Those metrics never reach the valuation today,
   which still uses a flat `rent_growth = 0.03`.
2. **Factor interactions matter** (`PolynomialFeatures(interaction_only=True)`). Income growth in a
   supply-constrained market means something different than in an unconstrained one. Test it
   explicitly rather than assuming additivity.
3. **Per-year growth vectors** (`rental_growth[year-1]`). Both prior models vary growth by year; the
   current engine compounds a single scalar. `proforma.py` accepts `float | list[float]` for every
   growth factor.
4. **Entry vs. exit cap rate** (`cap_rate_in` / `cap_rate_out`). The current engine has no cap rate
   in the projection at all. Cap-rate movement between purchase and sale is one of the largest
   drivers of realised return and belongs in the tornado.
5. **Scenario spread derived from factor exposure and volatility** — the prototype's
   `avg_factor = sum(feature x correlation)`, scaled by each factor's historical volatility.
   Replaces `Assumptions.scenario_spread = 0.02`, a hardcoded +/-2pp identical for every property in
   every market.
6. **Path dynamics: cycles, shocks, random walk.** A sinusoidal cycle, a 10%-probability jump shock,
   and a random-walk term model how markets actually move. See section 5.
7. **Implied rent from cap rate**: `price x cap_in / ((1-opex)(1-vac)) / 12`. A free sanity check —
   when observed market rent diverges sharply from cap-rate-implied rent, either the ask or the rent
   assumption is wrong. Surface it as a flag.
8. **Normalise factors before combining** (`MinMaxScaler`). The same instinct as this project's
   percentile scoring — confirmation the existing approach is sound.
9. **NPV at a stated discount rate alongside IRR.** The workbook reports IRR only. IRR alone is
   misleading when comparing deals of different size or duration.
10. **Cross-market comparison** across many cities — the same comparison the Phase 1 tract model is
    meant to enable.
11. **Growth-path chart** (base/bull/bear by year), for Institutional mode, following the `dataviz`
    skill.

---

## 4. Design rules these two models argue for

- **Derived values are never free-hand inputs.** Depreciable basis is computed from price,
  capitalized costs and land allocation — never typed in. A standalone basis field can silently
  disagree with the deal by a large multiple.
- **No constants below the input block.** Every cell downstream of assumptions stays a live formula,
  in the engine and in the exported workbook.
- **Simulation writes to a results sheet, never back into the model.**
- **Tax inputs are validated against statutory ceilings** — unrecaptured Section 1250 gain is capped
  at 25%; long-term capital gain tops out at 20% + 3.8% NIIT. An out-of-range rate is rejected, not
  quietly compounded.
- **Vacancy reduces income once.** Downside is modelled by varying the rate, not by zeroing net cash
  flow — a vacant year still owes debt service and operating expenses.
- **Loss deductibility is an election, not an assumption.** Whether a rental loss is currently
  deductible depends on Section 469, the $25k active-participation allowance (phasing out over
  $100k-$150k MAGI), and the real-estate-professional exception. The model exposes the choice.
- **Validate temporally, against real outcomes.** The prototype was trained entirely on synthetic
  data, so nothing it produced was ever tested against reality. Every fitted factor here trains only
  on data predating each test sale and is scored by `app/valuation/eval.py`.
- **Prefer explainable models.** A valuation defended in a memo needs visible coefficients. Start
  with ridge/OLS over the Growth Score metrics — implementable in the `numpy`/`pandas` already
  present — and adopt `scikit-learn`/`xgboost` only if `eval.py` shows a tree model measurably wins.

---

## 5. Note on the current Monte Carlo

Reviewing `app/valuation/scenarios.py:213` against the prototype exposed three real limitations in
the *existing* implementation, worth recording because they are not obvious from the code:

1. It samples each factor **independently** (`rng.triangular` per factor). Rates, cap rates and
   appreciation move together in reality; independent draws understate tail risk.
2. It draws **one constant value per factor per trial**, so every trial is a world where rent grows
   at exactly one rate for ten years. No cycles, no mean reversion, no shocks.
3. It only randomizes factors that are **market-backed** (`est is not None`). Since four of five
   factors are currently unbacked (`research/gaps.json`), Monte Carlo is effectively varying **one**
   factor, and the output distribution is far narrower than reality.

Items 1-2 are fixed by the prototype's path-based, correlated approach. Item 3 is fixed by closing
the gaps in `research/gaps.json` — `interest_rate` first, since FRED `MORTGAGE30US` is free and
keyless.
