# HUD Fair Market Rents (FMR) API

**Date:** 2026-10-26 · **Candidate file:** `research/candidates/hud-fair-market-rents.json`

## What it is
HUD's annual estimate of gross rent by bedroom count at the 40th percentile of a metro or county
rental market, used to set Section 8 payment standards. Standard geography is metro (CBSA) or county;
Small-Area FMRs (SAFMR) exist at ZIP level for some designated metros. Requires a free HUD User
account and access token (confirmed via HUD's own dataset page text reported in search results); its
API Terms of Service reportedly require an attribution notice in any app that uses it.

## Why it could help
A second, government-sourced rent benchmark, in-scope per this run's instructions (HUD named
explicitly). Could in principle supplement `app/sources/zillow_research.py`'s ZORI.

## Evaluation
Not run (`app/research/evaluate_series.py` doesn't exist yet in this repo).

## The coverage problem, stated plainly
`zillow_research.py` already provides ZORI at ZIP level for NYC, rolled up to NTA by a sale-weighted
mapping, and `investment.py`'s `neighborhood_rent` is fed from that today. FMR's standard geography is
metro/county — for NYC that would likely resolve to **one number for the whole city** unless NYC is
confirmed as a Small-Area FMR metro (not confirmed in this research pass). That would make it
strictly coarser than the rent signal this app already has.

## Verification caveat
huduser.gov returned `403 connect_rejected` from this session's proxy. Findings are from WebSearch
summaries of HUD's dataset page and third-party API wrappers (hudpy, rhud, hudr), not a direct fetch
of `fmr-api.html` or the ToS page. Confirm whether NYC has SAFMR (ZIP-level) coverage before writing
this off entirely — that's the one fact that could flip this recommendation.

## Recommendation: **Don't recommend** (for now)
ZORI already covers NYC rents at finer granularity than standard FMR would provide, and FMR adds a
token-gated dependency (plus an attribution obligation to satisfy) for a signal this app already has.
The genuine case for FMR is smaller metros where Zillow's ZIP-level ZORI gets thin or doesn't exist —
which only matters once the project generalizes past NYC. Revisit then, and specifically check SAFMR
coverage for NYC before fully ruling it out.
