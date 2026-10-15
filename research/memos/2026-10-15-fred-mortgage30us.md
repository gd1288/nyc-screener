# FRED MORTGAGE30US -- research memo

**Date:** 2026-10-15 | **Candidate file:** `research/candidates/fred-mortgage30us.json` | **Recommendation: REJECT**

## What it is
Freddie Mac's weekly Primary Mortgage Market Survey (30-year fixed rate), distributed through the
Federal Reserve's FRED API/series `MORTGAGE30US`.

## Why it looked promising
`backend/app/scoring/investment.py`'s `Assumptions.interest_rate` is a hardcoded `0.065` constant
used in every mortgage-payment, cash-flow, and Opportunity Score calculation this project produces.
A live weekly national mortgage-rate feed is about as direct a fit for a stated gap as this kind of
research turns up -- free, no login wall (a free API key, same pattern as the Census ACS source
already in this project), weekly cadence, long history.

## Why it's disqualified
FRED updated its API Terms of Use in June 2024. Per FRED's own announcement of that change
(`news.research.stlouisfed.org/2024/06/weve-updated-our-terms-of-use-action-requested`), the update
added explicit API prohibitions on:
1. storing, caching, or archiving any portion of FRED Content, and
2. using the API in connection with developing or training any software/ML/AI system.

This project's source adapters all write their ingested series into `backend/data/screener.db`
(SQLite) for later querying and scoring -- that is exactly the kind of storage/caching/archiving the
updated terms bar, and that alone is a license problem under this project's "no clause blocking
commercial/product use" bar. (The update's separate ML/AI prohibition is aimed at using FRED content
as training data for a model -- it isn't about an AI tool writing the adapter code, so it isn't
being counted as a second strike here; the storage/caching clause carries the rejection on its own.)

Note: I could not fetch the literal clause text directly (`fred.stlouisfed.org` was unreachable from
this environment -- DNS resolution failed), so this call rests on FRED's own public summary of the
change rather than the raw legal text. If someone wants to pursue this further, re-verify the exact
wording before relying on this conclusion either way.

## Recommendation
Don't implement. If a live mortgage-rate input is still wanted, a follow-up research pass (not done
here -- over this run's search budget) could look at sources that don't carry FRED's redistribution
restriction, e.g. Freddie Mac's own PMMS page directly, or another public rate index not gated
through FRED's terms.
