#!/usr/bin/env python3
"""Snapshot the local screener's active listings into docs/artifact/staging.html.

The artifact cannot call the backend (its sandbox blocks network requests), so the screener drawer
is fed by a trimmed snapshot embedded between the LISTINGS-START/END markers. Numbers come from the
backend's own analysis, never recomputed here: rent, taxes and common charges are the unrounded
`analysis.exact` values, and `est` carries the backend's `estimated_fields` so the page can label
estimates honestly. Re-run to refresh; writes docs/artifact/listings.json as well.

Also embeds the market context (mortgage rate, 10-year Treasury, NYC price drawdown) from the stored FRED
series between MARKET-START/END. Usage: cd backend && uv run python ../scripts/embed_screener.py   (add --html PATH to target another file)
"""
import json
import re
import sys
import warnings
from datetime import date
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AppSetting, Listing  # noqa: E402
from app.pipeline.listing_urls import URLS_KEY, is_allowed_url  # noqa: E402
from app.services import MarketContext  # noqa: E402
from app.sources.fred import FRED_NOTICE  # noqa: E402
from app.valuation import macro as macro_mod  # noqa: E402
from app.valuation.factors import _percentile  # noqa: E402


def market_block() -> dict | None:
    """Live rate context from the stored FRED series, or None when the macro sources have not run."""
    with SessionLocal() as session:
        macro = MarketContext.load(session).macro
    summary = macro_mod.summary(macro)
    if "mortgage30" not in summary:
        return None
    vals = sorted(v for _, v in macro["MORTGAGE30US"]["points"])
    summary["rate_range"] = {q: round(_percentile(vals, p) / 100, 4) for q, p in (("p10", 0.1), ("p50", 0.5), ("p90", 0.9))}
    hp = (macro.get("ATNHPIUS35614Q") or {}).get("points") or []
    summary["history_start"] = hp[0][0][:4] if hp else None
    summary["notice"] = FRED_NOTICE
    return summary


def closed_rows(client: TestClient) -> list[dict]:
    """Listings that left the market (sold, off market, withdrawn), from the backend's own lifecycle fields."""
    with SessionLocal() as session:
        loc = {i: (b, lat, lon) for i, b, lat, lon in session.query(Listing.id, Listing.bbl, Listing.latitude, Listing.longitude)}
        found = session.get(AppSetting, URLS_KEY).value if session.get(AppSetting, URLS_KEY) else {}
    rows = []
    for s in client.get("/api/listings", params={"status": "closed", "include_coops": "false"}).json():
        bbl, lat, lon = loc.get(s["id"], (None, None, None))
        f = found.get(str(s["id"])) or {}
        rows.append({
            "id": s["id"], "a": s["address"], "u": s["unit"], "h": s["neighborhood"], "b": s["borough"], "st": s["status"],
            "p": s["price"], "op": s["original_price"], "sp": s["sold_price"], "sd": s["sold_date"], "od": s["off_market_date"],
            "vl": s["sold_vs_list_pct"], "dom": s["days_on_market"], "bd": s["bedrooms"], "sf": s["sqft"],
            "bbl": bbl, "lat": lat, "lon": lon,
            "lu": f.get("url") if is_allowed_url(f.get("url") or "") else None, "ll": f.get("level"),
        })
    return rows


def trimmed(client: TestClient, rate: float | None) -> tuple[list[dict], dict]:
    """One row per screener listing. When `rate` is given, the backend's own analysis is re-run at that
    mortgage rate (POST /analyze), so its IRR/cap/cash-on-cash are comparable to the artifact's tool."""
    rows, assump = [], {}
    with SessionLocal() as session:
        loc = {i: (b, lat, lon) for i, b, lat, lon in session.query(Listing.id, Listing.bbl, Listing.latitude, Listing.longitude)}
        missed = dict(session.query(Listing.id, Listing.missed_fetches))
        found = (session.get(AppSetting, URLS_KEY).value if session.get(AppSetting, URLS_KEY) else {})
    for s in client.get("/api/listings").json():
        d = client.post(f"/api/listings/{s['id']}/analyze", json={"interest_rate": rate} if rate else {}).json()
        ex, an = d["analysis"]["exact"], d["analysis"]
        a = an["assumptions"]
        assump = {"dp": a["down_payment_pct"], "rate": a["interest_rate"], "years": a["loan_years"], "vac": a["vacancy_pct"],
                  "mgmt": a["management_pct"], "rg": a["rent_growth"], "eg": a["expense_growth"], "exit": a["exit_cost_pct"]}
        bbl, lat, lon = loc.get(s["id"], (None, None, None))
        rows.append({
            "id": s["id"], "a": s["address"], "u": s["unit"], "h": s["neighborhood"], "b": s["borough"],
            "p": s["price"], "bd": s["bedrooms"], "ba": s["bathrooms"], "sf": s["sqft"], "yb": s["year_built"],
            "dom": d["days_on_market"], "cut": d["price_cuts"], "new": bool(d["is_new"]),
            "gs": d["growth_score"], "os": d["opportunity_score"], "own": d["ownership"],
            "bbl": bbl, "lat": lat, "lon": lon,
            "ms": missed.get(s["id"]) or 0,  # consecutive complete feed checks that did not include this listing
            # listing page found by search (link only); re-validated here so nothing unchecked reaches the page
            "lu": (found.get(str(s["id"])) or {}).get("url") if is_allowed_url((found.get(str(s["id"])) or {}).get("url") or "") else None,
            "ll": (found.get(str(s["id"])) or {}).get("level"),
            # unrounded backend inputs (monthly) and what the backend itself concludes at the same rate
            "rent": round(ex["rent"], 2), "cc": round(ex["common_charges"], 2), "tax": round(ex["property_taxes"], 2),
            "ins": a["insurance_monthly"], "mnt": a["maintenance_monthly"],
            "est": an["estimated_fields"], "pc": an["purchase_costs"]["total"],
            "cap": round(d["cap_rate"], 4), "irr": d["irr_10y_base"], "coc": round(d["cash_on_cash"], 4),
        })
    return rows, assump


def main() -> int:
    html_path = Path(sys.argv[sys.argv.index("--html") + 1]) if "--html" in sys.argv else ROOT / "docs/artifact/staging.html"
    # No `with`: entering the client would run the app's lifespan and start its refresh scheduler.
    market = market_block()
    rows, assump = trimmed(TestClient(app), market["mortgage30"]["rate"] if market else None)
    rows = [r for r in rows if r["own"] != "likely_coop"]
    payload = {"as_of": date.today().isoformat(), "assump": assump, "rows": rows}
    mblob = json.dumps(market, separators=(",", ":"))
    sold = {"as_of": date.today().isoformat(), "rows": closed_rows(TestClient(app))}
    sblob = json.dumps(sold, separators=(",", ":"))
    (ROOT / "docs/artifact/listings.json").write_text(json.dumps(payload, separators=(",", ":")))
    blob = json.dumps(payload, separators=(",", ":"))
    html = html_path.read_text()
    pat = re.compile(r"/\*LISTINGS-START\*/.*?/\*LISTINGS-END\*/", re.S)
    if not pat.search(html):
        print("markers /*LISTINGS-START*/ .. /*LISTINGS-END*/ not found in", html_path)
        return 1
    html = pat.sub(lambda _: f"/*LISTINGS-START*/const LISTINGS={blob};/*LISTINGS-END*/", html)
    mpat = re.compile(r"/\*MARKET-START\*/.*?/\*MARKET-END\*/", re.S)
    if not mpat.search(html):
        print("markers /*MARKET-START*/ .. /*MARKET-END*/ not found in", html_path)
        return 1
    html = mpat.sub(lambda _: f"/*MARKET-START*/const MARKET={mblob};/*MARKET-END*/", html)
    spat = re.compile(r"/\*SOLD-START\*/.*?/\*SOLD-END\*/", re.S)
    if not spat.search(html):
        print("markers /*SOLD-START*/ .. /*SOLD-END*/ not found in", html_path)
        return 1
    html_path.write_text(spat.sub(lambda _: f"/*SOLD-START*/const SOLD={sblob};/*SOLD-END*/", html))
    print(f"market context: {'live rate ' + str(market['mortgage30']['rate']) if market else 'none (macro sources have not run)'}")
    print(f"closed listings: {len(sold['rows'])}")
    print(f"embedded {len(rows)} listings ({len(blob) // 1024} KB) as of {payload['as_of']} into {html_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
