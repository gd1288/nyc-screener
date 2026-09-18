# Plan: "Purchase property" analysis page (staging artifact)

Status: designed 2026-09-18, awaiting the user's answers to the questions at the end. Not built.

## What the user asked for
A "Purchase property" button. Pressing it runs an analysis of what owning that property would actually cost: the cash needed to
buy it, every monthly obligation, and the costs across the whole life of owning it. The user has no fixed design in mind, so
options come first and nothing is built until one is chosen.

## What the tool already knows (so the page can be built without new data)
- **One-time, at purchase:** down payment; NYC closing costs itemised by the backend (`purchase_costs`): mansion tax (1% at
  $1M and up), mortgage recording tax (about 1.8% of the loan), title insurance, attorney and bank fees. The artifact carries
  these as a single percentage (`txnPct`) today, so the page needs the itemised split.
- **Monthly:** mortgage principal and interest (amortisation), property tax (0.9% of price a year when the listing has none),
  common charges (listed, or estimated at $1.10 per sq ft), insurance ($60), maintenance ($100), management and vacancy
  (percent of rent, only if rented). Each carries the market-backed / derived / unbacked chip already used elsewhere.
- **Over time:** growth rates for rent, expenses and tax; loan balance by year; hold period (10 years) and loan term (30).
- **At sale:** selling costs, loan payoff, taxes on the sale (the artifact's are simplified versus `taxes.py`).

## Not modelled today (the page should say so, and let the user add them)
Utilities; renovation and capital repairs; special assessments; mortgage insurance when the down payment is under 20%; flood
insurance; moving and furnishing; and **rental restrictions** (many NYC condos limit or ban renting, which matters most for an
investor and is a check the user must do with the building).

## Design options
1. **Purchase plan page (a new tab)** *(recommended).* A full page, in this order:
   a. Summary strip: **Cash to close**, **Monthly cost (year 1)**, **Total cost over your hold**.
   b. **Cash you need at closing:** down payment plus each closing cost as a line, with a bar and a total.
   c. **What you pay every month:** mortgage split into principal and interest, property tax, common charges, insurance,
      maintenance, then management and vacancy if rented. A toggle switches "Live in it" (gross costs) and "Rent it out"
      (net of rent).
   d. **The life of owning it:** a year slider (1 to 30). Columns per year show the costs stacked, a line shows loan balance
      and equity built, and a table lists every year. Milestones are called out: principal overtakes interest, cash flow turns
      positive or negative, loan paid off.
   e. **When you sell:** selling costs, loan payoff, taxes, net proceeds.
   f. **Add your own costs:** utilities, renovation, special assessment, mortgage insurance, each with an amount and frequency.
   g. **Not included** checklist (the list above) with plain-language prompts.
2. **Guided walkthrough.** Four steps (Financing, Closing, Owning, Selling), one card at a time. Easier to follow for a
   first-time buyer; slower for someone comparing many properties.
3. **12-month cash calendar.** A month-by-month grid: the lump sum at closing, then each month's outflow, with quarterly
   tax bills and annual insurance landing when they fall due. Best for judging how much cash to hold in reserve. Works well
   as one collapsible section inside option 1.
4. **Ownership statement.** One long, printable page laid out like a bank statement, for sharing with a lender or partner.
   Can be added to option 1 later as a "Print / save as PDF" view.

**Recommendation:** option 1, with the 12-month calendar as a collapsible section and a print view later.

## Where it lives and how it behaves
- **Entry points:** a "Purchase property" button in the deal header (beside Browse screener) and an "Analyze purchase" action on
  each screener row. It analyses whatever is loaded, instantly, from the current inputs (no waiting), and reuses the same
  editable inputs so amending price, rate or down payment updates the page.
- **Tab:** added at the end of the tab strip so the four locked tabs and their order do not change (needs the user's OK,
  and the main artifact is only changed by promotion).
- **Every line has an info marker** that opens its formula (see `docs/plans/formulas-tab.md`), so "where does this number come
  from" is one click away.
- **Backend:** the itemised plan should come from a new backend function (`app/valuation/purchase.py`) that returns the line
  items, so the artifact and the future app share it. The artifact keeps a matching in-page version (as with `model()`), and a
  parity test compares them.
- **Honesty:** rent, property tax and (where missing) common charges are estimates; the page keeps those chips and a short
  "not financial advice" line.

## Questions for the user (answer these before building)
1. **Will you live in it or rent it out?** This decides the default view: gross monthly cost, or cost net of rent.
2. **Which extra costs matter to you?** Utilities, renovation, special assessments, mortgage insurance, others.
3. **Which time horizons?** Your hold period (10 years), the full loan (30 years), or both with a toggle.
4. **Do you want an Excel export, a printable page, or neither for now?** The backend already has an Excel export.
5. **Is this a what-if only,** or should "Purchase property" also record a property you actually bought so you can track it?

## Prompt for a new window
```
You are continuing the nyc-screener project. Nothing is remembered from other windows except what is in the repo. Read, in
order: CLAUDE.md, docs/NEXT.md, docs/UI.md (especially "Picking this up in a new window"), docs/DECISIONS.md,
docs/ARCHITECTURE.md, docs/plans/purchase-analysis.md (this plan and the user's answers to its questions), and
docs/plans/formulas-tab.md. Build the "Purchase property" page on the STAGING artifact only (docs/artifact/staging.html). The
main artifact is locked. Rules: additive changes only; the backend is the only calculation engine (add
app/valuation/purchase.py with tests and a parity check); no scraping; never touch the LISTINGS/MARKET/SOLD data blocks by
hand; test with docs/artifact/checks/staging_sweep.js and a 400px iframe; run pytest, ruff and app.cli status; update
docs/UI.md and docs/DECISIONS.md; commit with the Co-Authored-By line. Stop and ask before adding the tab to the tab strip.
```
