# NYC Condo Screener

A screener and investment-analysis tool for NYC condos. It tracks listings (new, price changes, days on market,
sold), scores every neighborhood on 10–20 year growth potential, and models each condo as an investment
(cash flow, cap rate, 10/20-year IRR under bear/base/bull scenarios).

## Run it

```bash
./start.sh
```

Then open http://localhost:3000. The first time, click **Refresh now** (top right) to load all data (~5 minutes).
While the backend is running, each source refreshes on its own schedule (see `backend/sources.yaml`).

## API keys (all free, optional)

Put them in `.env` in this folder, then restart:

| Key | Unlocks | Sign up |
|---|---|---|
| `RENTCAST_API_KEY` | Automatic daily discovery of new condo listings (free tier ≈ 50 requests/month) | https://app.rentcast.io/app/api |
| `CENSUS_API_KEY` | Demographics pillar (population, income, education, age trends) | https://api.census.gov/data/key_signup.html |
| `SOCRATA_APP_TOKEN` | Higher rate limits on NYC Open Data (works without it) | https://data.cityofnewyork.us/profile/edit/developer_settings |

Without RentCast you can still add listings by hand or CSV on the **Add listings** page.

## Pages

- **Screener**: active listings ranked by Opportunity Score, with filters and a map.
- **Sold & off-market**: listings that left the market; sales are confirmed from recorded ACRIS deeds.
- **Listing detail**: price history, editable investment model, comps from the same building, neighborhood breakdown.
- **Neighborhoods**: growth-score rankings, adjustable weights, and the backtest.
- **Compare**: two neighborhoods side by side, with how much each driver contributes to the gap (defaults to FiDi vs Chelsea).
- **Data sources**: freshness and status of every source, plus buttons to run each one.

## How the scores work

**Neighborhood Growth Score (0–100)**: each metric becomes a percentile across NYC's residential neighborhoods,
metrics roll up into pillars, and pillars are combined with weights you can edit:

| Pillar | Default weight | Metrics |
|---|---|---|
| Valuation gap | 25 | Discount to borough and adjacent neighborhoods, gross rent yield |
| Development pipeline | 20 | Units in the permit pipeline, units completed in 5 yrs, area upzoned in 10 yrs |
| Infrastructure | 15 | Planned catalysts (`backend/catalysts.yaml`), subway routes, distance to subway |
| Demographics | 15 | Population and income growth, change in bachelor's-degree share, share aged 25–34 (needs Census key) |
| Momentum | 5 | Condo value growth (5/10 yr), repeat-sale appreciation, rent growth, sales volume |
| Commercial | 10 | Share of liquor licenses issued recently, license density |
| Safety | 10 | Felonies per 1,000 homes and their 5-year trend |
| Flood risk | −15 pts max | Share of area in the 2050s 100-year floodplain |

Default weights come from the backtest (`uv run python -m app.cli backtest`). Using only data available at the start of
each period, the valuation gap predicted the next 10 years of condo growth in every period tested (rank correlation
0.20–0.41, 2008–2024), while recent momentum mostly reversed. A pillar with no data counts as neutral (50).

**Opportunity Score** = 50% neighborhood growth + 25% value vs comps + 25% rental yield.

**Investment model**: NYC mansion tax and mortgage recording tax, sponsor transfer taxes for new development,
common charges, taxes, vacancy, management, mortgage amortization, and exit costs. Appreciation blends the citywide
10-year condo trend with the neighborhood's own trend, adjusted ±1 pt/yr by growth score. Fields the listing doesn't
provide (rent, taxes, common charges) are estimated and flagged in the UI.

## Adding a data source

1. Create `backend/app/sources/my_source.py` with a class that subclasses `Source` (see `app/sources/base.py`):
   - `kind = "neighborhood"`: call `self.write_metrics(ctx, {"metric": {nta_code: value}}, as_of)`.
   - `kind = "listings"`: build `RawListing`s and call `sync_listings(...)` (handles new, price changes, off market).
2. Add it to `backend/sources.yaml` with a cron `schedule`.
3. To score a new metric, add a `MetricDef` to a pillar in `app/scoring/neighborhood.py`.

## Data sources

NYC Open Data: 2020 neighborhood boundaries, DOF condo sales, ACRIS deeds, DCP Housing Database, Mandatory
Inclusionary Housing rezonings, NYPD complaints, 2050s floodplain. data.ny.gov: MTA subway stations, State Liquor
Authority licenses. Zillow Research (ZHVI condo values, ZORI rents). US Census ACS. RentCast. NYC GeoSearch
(address → coordinates + BBL). OpenFreeMap basemap.

## Development

```bash
cd backend && uv run pytest                 # tests
cd backend && uv run python -m app.cli refresh [source ...]
cd frontend && npx tsc --noEmit && npm run lint
```

Data lives in `backend/data/screener.db` (SQLite). To use Postgres, set `DATABASE_URL` in `.env`.
