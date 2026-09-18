#!/usr/bin/env python3
"""Snapshot the local screener's active listings into docs/artifact/staging.html.

The artifact cannot call the backend (its sandbox blocks network requests), so the screener drawer
is fed by a trimmed snapshot embedded between the LISTINGS-START/END markers. Numbers come from the
backend's own analysis, never recomputed here: rent, taxes and common charges are the unrounded
`analysis.exact` values, and `est` carries the backend's `estimated_fields` so the page can label
estimates honestly. Re-run to refresh; writes docs/artifact/listings.json as well.

Usage: cd backend && uv run python ../scripts/embed_screener.py   (add --html PATH to target another file)
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

from app.main import app  # noqa: E402


def trimmed(client: TestClient) -> tuple[list[dict], dict]:
    rows, assump = [], {}
    for s in client.get("/api/listings").json():
        d = client.get(f"/api/listings/{s['id']}").json()
        ex, an = d["analysis"]["exact"], d["analysis"]
        a = an["assumptions"]
        assump = {"dp": a["down_payment_pct"], "rate": a["interest_rate"], "years": a["loan_years"], "vac": a["vacancy_pct"],
                  "mgmt": a["management_pct"], "rg": a["rent_growth"], "eg": a["expense_growth"], "exit": a["exit_cost_pct"]}
        rows.append({
            "id": s["id"], "a": s["address"], "u": s["unit"], "h": s["neighborhood"], "b": s["borough"],
            "p": s["price"], "bd": s["bedrooms"], "ba": s["bathrooms"], "sf": s["sqft"], "yb": s["year_built"],
            "dom": s["days_on_market"], "cut": s["price_cuts"], "new": bool(s["is_new"]),
            "gs": s["growth_score"], "os": s["opportunity_score"], "own": s["ownership"],
            # unrounded backend inputs (monthly) and what the backend itself concludes
            "rent": round(ex["rent"], 2), "cc": round(ex["common_charges"], 2), "tax": round(ex["property_taxes"], 2),
            "ins": an["assumptions"]["insurance_monthly"], "mnt": an["assumptions"]["maintenance_monthly"],
            "est": an["estimated_fields"], "pc": an["purchase_costs"]["total"],
            "cap": round(s["cap_rate"], 4), "irr": s["irr_10y_base"], "coc": round(s["cash_on_cash"], 4),
        })
    return rows, assump


def main() -> int:
    html_path = Path(sys.argv[sys.argv.index("--html") + 1]) if "--html" in sys.argv else ROOT / "docs/artifact/staging.html"
    # No `with`: entering the client would run the app's lifespan and start its refresh scheduler.
    rows, assump = trimmed(TestClient(app))
    rows = [r for r in rows if r["own"] != "likely_coop"]
    payload = {"as_of": date.today().isoformat(), "assump": assump, "rows": rows}
    (ROOT / "docs/artifact/listings.json").write_text(json.dumps(payload, separators=(",", ":")))
    blob = json.dumps(payload, separators=(",", ":"))
    html = html_path.read_text()
    pat = re.compile(r"/\*LISTINGS-START\*/.*?/\*LISTINGS-END\*/", re.S)
    if not pat.search(html):
        print("markers /*LISTINGS-START*/ .. /*LISTINGS-END*/ not found in", html_path)
        return 1
    html_path.write_text(pat.sub(lambda _: f"/*LISTINGS-START*/const LISTINGS={blob};/*LISTINGS-END*/", html))
    print(f"embedded {len(rows)} listings ({len(blob) // 1024} KB) as of {payload['as_of']} into {html_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
