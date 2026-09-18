# Data source licenses and legal decisions

One row per source: what the terms say, what we do about it, and where the terms were read. Reviewed
2026-09-18 by reading each provider's own terms pages (links below), not summaries. **This is a personal,
single-user tool.** Several sources below change status if the app is ever shared or made public;
revisit this file before that happens. Not legal advice.

Rule for every new source: read the terms first, add a row here, and use only documented APIs or
files the provider publishes for download. Never scrape pages, and never automate against a site whose
terms forbid automated access.

## Sources added or decided in this pass
| Source | Decision | Terms and what they mean for us |
|---|---|---|
| **FRED API** (mortgage rate, series MORTGAGE30US) | **Built** (`app/sources/fred.py`); runs once a free key is set | [FRED API terms](https://fred.stlouisfed.org/docs/api/terms_of_use.html): free key; must display "This product uses the FRED(R) API but is not endorsed or certified by the Federal Reserve Bank of St. Louis."; may not imply endorsement or replicate FRED's own site. Caching is not addressed in the terms; we keep only a rolling ~5 years of one series. Documented API only, one request per series per run. |
| **Freddie Mac PMMS** (the data behind MORTGAGE30US) | Used, with attribution, personal use only | [Freddie Mac PMMS](https://www.freddiemac.com/pmms): "may be used with proper attribution. Alteration ... is strictly prohibited." FRED's terms add that third-party series used beyond your own personal use need the owner's permission. **Ask Freddie Mac before sharing or publishing the app.** Citation is stored with the data: "Freddie Mac, 30-Year Fixed Rate Mortgage Average in the United States [MORTGAGE30US], retrieved from FRED, Federal Reserve Bank of St. Louis; https://fred.stlouisfed.org/series/MORTGAGE30US". It is an owner-occupied rate; investor loans price higher (the factor's source text says so). |
| **FRED: 10-year Treasury (DGS10)** | **Built** (same adapter) | Board of Governors of the Federal Reserve System; FRED tags it "Public Domain: Citation Requested". Citation stored with the data. |
| **FRED: FHFA New York metro price index (ATNHPIUS35614Q)** | **Built** (same adapter) | U.S. Federal Housing Finance Agency data; the series' own notes carry no copyright statement and it is tagged "Public Domain: Citation Requested" (one page read said "copyrighted" generically, so attribution is kept and use stays personal). History from 1975, quarterly. Used only to report how far New York prices actually fell, as a reality check on scenario severity. |
| **FRED: Case-Shiller NY (NYXRSA)** | **Rejected** | S&P Dow Jones Indices: reproduction prohibited without prior written permission (index_services@spdji.com). |
| **Perplexity Search API** (finding listing-page links) | **Built, dormant until you add a key** (`app/pipeline/listing_urls.py`, `app.cli find-listing-urls`) | [Search API docs](https://docs.perplexity.ai/guides/search-quickstart): POST, Bearer key, up to 20 allowed domains, returns title/URL/snippet; about **$5 per 1,000 requests** ([pricing summary](https://developer.puter.com/tutorials/perplexity-api-pricing/)), so all 246 listings cost about $1.23. **I could not read Perplexity's own Search Service terms (its page returns 403 to my tools). Read [the terms](https://www.perplexity.ai/hub/legal/perplexity-api-terms-of-service-search) when you sign up.** What a search snippet of their ToS says: output may be displayed solely within your own application, and building a competing product is prohibited; this use (a private app showing a link) fits, but confirm. Safeguards in code: only Perplexity is called (never a listing site); only the URL is kept and result text is discarded; https and a 10-domain allowlist only; the URL must contain the property's street number and street name; monthly cap of 300 requests; key in a header, never in a URL. |
| **Listing sites** (Zillow, StreetEasy, Redfin, Realtor.com) | **Link only, never fetched** | [Zillow Terms of Use](https://www.zillow.com/corporate/terms-of-use/) and [Redfin Terms](https://www.redfin.com/about/terms-of-use) prohibit automated queries, scraping and data mining; StreetEasy actively blocks bots (its terms text could not be retrieved, treated as the same). No code here requests these sites. The UI builds a link and your own browser opens it. Only URLs are stored, never listing content (price, photos, descriptions), which is the data those terms protect. |
| **HUD Fair Market Rents API** | Approved, **not built** | US government data; free token; [terms page](https://www.huduser.gov/portal/dataset/api-terms-of-service.html) and the API docs could not be read by the fetch tool (page renders in JavaScript), so read them by hand before building. Reported limit: 60 queries/min. |
| **NYC Rent Guidelines Board operating-cost index** | Approved, **blocked** | Public NYC agency report ([RGB research](https://rentguidelinesboard.cityofnewyork.us/research/)). Blocked on data extraction, not on legality: the table is inside PDFs and this environment has no PDF tooling. The 4.1% figure is the RGB's projection for the coming lease year, not a measured history, so it is not used as a factor yet. |
| **Apartment List rent estimates** | **On hold** | Publishes free CSVs "to the general public" ([data page](https://www.apartmentlist.com/research/category/data-rent-estimates)) but no license, attribution or automated-download terms could be found. Ask research@apartmentlist.com before ingesting. Zillow ZORI (already loaded) covers rent growth meanwhile. |
| **Redfin Data Center** | **Rejected** | [Redfin Terms of Use](https://www.redfin.com/about/terms-of-use) s.2.3.5 forbids automated crawling or querying "for any purpose" without written permission, and the services addendum forbids scraping and data mining. The Data Center is a manual-download product; scripting it would be automated access. Manual, occasional use with a citation is a separate personal choice. |
| **Walk Score API** | **Rejected** | [Free tier](https://www.walkscore.com/professional/api-sign-up.php) is "for free consumer-facing applications only" and caching is a paid feature. A private analysis tool does not qualify. |

## Sources already in the project (not re-reviewed in this pass)
RentCast (plan terms: [rentcast.io/api](https://www.rentcast.io/api), "flexible licensing", no attribution
required; only through `rentcast.py`); Zillow Research CSVs (usage text has been removed from their page;
keep attribution); Census ACS and TIGERweb (public domain); FHFA HPI (public); NYC Open Data / Socrata
datasets (city open data terms); MTA, NYPD, DOF, ACRIS (via NYC Open Data). Confirm any of these before
the app is shared publicly.

## Links shown in the UI
The links menu only *builds* web addresses for your own browser to open; nothing is fetched or scraped.
Official-record links (NYC Planning ZoLa, NYC Finance ACRIS) and map links (Google Maps URLs API) use each
provider's documented address patterns; the ACRIS pattern is from third-party documentation and is unverified.
Search links point to a search page for the address on Zillow and (via Google) StreetEasy, never to scraped data.
ACRIS itself blocks automated tools, so no code here or in scripts requests ACRIS pages: the project's ACRIS data
comes from NYC Open Data.
