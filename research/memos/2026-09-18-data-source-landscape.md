# Data source landscape and costs (researched 2026-09-18)

Sources: vendor pages and web search on 2026-09-18. Figures marked (3rd party) come from review/aggregator
sites, not the vendor, and must be confirmed before committing money. Nothing here is approved; free
candidates are logged in `research/registry.json` as `proposed`.

## Project rule that limits the field
No scraping of listing sites. Third-party "Zillow API" / "Realtor API" wrappers on RapidAPI-style
marketplaces scrape those sites, so they are out even when they are cheap or have a free tier.

## RentCast (already used; only via `app/sources/rentcast.py`)
| Plan | Price | Requests/mo | Overage |
|---|---|---|---|
| Developer | $0 | 50 | $0.20 each |
| Foundation | $74 | 1,000 | $0.06 |
| Growth | $199 | 5,000 | $0.03 |
| Scale | $449 | 25,000 | $0.015 |
All endpoints on every plan (listings, rent/value AVM, property records, market stats). Billing is per request,
not per record; a listings request returns up to 500 records.

## Free candidates (mapped to the criteria ledger gaps)
| Gap | Source | Notes |
|---|---|---|
| interest_rate | FRED `MORTGAGE30US` (Freddie Mac, weekly) | Free API key, 120 requests/min. PLAN.md calls it keyless; that likely means FRED's CSV download link (unverified). |
| rent_growth | Apartment List rent estimates | Free CSVs: metro/county/city rents and monthly and annual growth back to 2017. Second opinion beside Zillow ZORI (already loaded). |
| rent_growth / rent level | HUD Fair Market Rents API | Free token. API is at FMR-area level; a ZIP crosswalk file gives small-area values. |
| vacancy | Census ACS (already wired) | Table B25004 vacancy status by tract. |
| expense_growth | NYC Rent Guidelines Board Price Index of Operating Costs | Annual PDF; 2026 projects +4.1%. NYC operating-cost inflation, but needs manual/PDF extraction. |
| market context | Redfin Data Center | Free bulk CSVs (days on market, price drops, sale-to-list); asks for a citation. |
| Zillow ZHVI/ZORI | Zillow Research | Already wired; 100+ free CSVs, monthly. Usage terms text has been removed from the page, so keep attribution. |
| walkability | Walk Score API | Free tier reported at 5,000 calls/day; requires attribution. |

## Paid options and what they would cost this project
| Provider | Price seen | Relevance |
|---|---|---|
| RentCast Foundation | $74/mo | Only if the free 50 becomes binding (on-demand rent AVM for many properties, or full-mode paging). |
| ATTOM | enterprise quote; (3rd party) $95/mo or $499/yr entry, $1k+/mo typical | Broadest property records; sales cycle, contract. Overkill for one user. |
| HouseCanary | app $19-$199/mo; API $0.05-$6.00 per call; institutional six figures (3rd party) | Strong AVM and forecasts; per-call cost depends on endpoint, confirm before use. |
| BatchData | from $1,000/mo for 100k records; $0.01 per call at the low end | Bulk-oriented; too large for this project. |
| Mashvisor | from $129/mo API | Short-term-rental analytics; weak fit for NYC condo sales. |
| Regrid parcels | not public (login to see); 30-day free sandbox | NYC parcels are free via PLUTO; matters only when adding other US metros. |
| Bridge Interactive (Zillow Group MLS API) | no fee, but needs MLS participant / vendor status | Not available to an individual investor. Third-party MLS aggregators start around $500/mo. |
| Reonomy | ~$400/mo per user (3rd party) | Owner and comps for multifamily/commercial (421 Harris type); only if that becomes core. |
| CoStar | ~$466+/mo per user (old forum figure, 3rd party) | Commercial comps; enterprise contract in practice. |

## Recommendation
Pay for nothing now. Wire FRED, Apartment List and the RGB operating-cost index for the four gap factors,
and spend spare RentCast requests (of the free 50) on on-demand rent estimates for properties actually opened
in valuation, cached in the database.

## More FRED series (checked on FRED's own pages 2026-09-18; same API key and terms as MORTGAGE30US)
| Series | What | Status on FRED | Use |
|---|---|---|---|
| DGS10 | 10-year Treasury yield, daily (Fed Board) | Public domain, citation requested | Benchmark for exit cap and discount rate; mortgage spread (6.95% mortgage vs 5.01% Treasury, about 1.9 pts, dates a day apart) |
| ATNHPIUS35614Q | FHFA All-Transactions HPI, NY-Jersey City-White Plains MSAD, quarterly since 1975 | US government | Real NYC drawdowns and recoveries to calibrate the 18 scenarios |
| RRVRUSQ156N | US rental vacancy rate, quarterly (Census) | Public domain, citation requested | National context only (7.3% Q2 2026) |
| CUSR0000SEHA | CPI rent of primary residence (BLS) | Marked copyrighted by FRED | Rent-growth reference, personal use only |
| NYXRSA | Case-Shiller New York HPI (S&P) | Copyrighted; reproduction prohibited without S&P's written permission | **Do not use** |
Not verified: my guess ATNHPIUS35620Q does not exist (404); NYC unemployment and metro GDP series IDs still need lookup.

