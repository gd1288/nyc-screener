"""Purchase plan: itemised closing costs, monthly obligations, ownership years, and the sale."""

import pytest

from app.scoring import investment as inv
from app.valuation.purchase import CustomCost, PurchaseInputs, plan


def _base(**kw):
    d = dict(price=800_000, down_pct=0.25, rate=0.065, term_years=30, horizon_years=10, tax_annual=7_000,
             common_monthly=700, rent_monthly=4_000)
    d.update(kw)
    return PurchaseInputs(**d)


def test_cash_to_close_is_down_payment_plus_the_backends_itemised_closing_costs():
    p = plan(_base())
    loan = 800_000 * 0.75
    closing = inv.purchase_costs(800_000, loan, inv.Assumptions())
    assert p["cash_to_close"]["down_payment"] == 200_000
    assert p["cash_to_close"]["closing_costs"] == closing
    assert p["cash_to_close"]["total"] == pytest.approx(200_000 + closing["total"])


def test_first_month_mortgage_matches_the_standard_payment_and_splits_into_interest_and_principal():
    p = plan(_base())
    pmt = inv.monthly_payment(600_000, 0.065, 30)
    m = p["monthly_year1"]
    assert m["mortgage_payment"] == pytest.approx(pmt)
    assert m["principal"] + m["interest"] == pytest.approx(pmt)
    assert m["interest"] > m["principal"]  # early in a 30-year loan the payment is mostly interest


def test_living_in_it_has_no_rent_and_renting_all_of_it_removes_owner_utilities():
    live = plan(_base(utilities_monthly=200))
    rent = plan(_base(utilities_monthly=200, phases=[{"from_year": 1, "share_rented": 1.0}]))
    assert live["monthly_year1"]["rent_in"] == 0 and live["monthly_year1"]["utilities"] == 200
    assert rent["monthly_year1"]["utilities"] == 0  # a tenant pays them when all of it is rented
    assert rent["monthly_year1"]["rent_in"] == pytest.approx(4_000 * 0.95)  # after 5% vacancy
    assert rent["monthly_year1"]["net_out"] < live["monthly_year1"]["net_out"]


def test_renting_one_room_of_three_collects_a_third_of_the_rent_and_the_owner_still_pays_utilities():
    p = plan(_base(utilities_monthly=150, phases=[{"from_year": 1, "share_rented": 1 / 3}]))
    assert p["monthly_year1"]["rent_in"] == pytest.approx(4_000 / 3 * 0.95)
    assert p["monthly_year1"]["utilities"] == 150


def test_live_first_then_rent_switches_the_income_and_costs_at_the_chosen_year():
    p = plan(_base(utilities_monthly=200, management_pct=0.05,
                   phases=[{"from_year": 1, "share_rented": 0.0}, {"from_year": 4, "share_rented": 1.0}]))
    y = {r["year"]: r for r in p["years"]}
    assert y[3]["rent_in"] == 0 and y[3]["utilities"] > 0 and y[3]["management"] == 0
    assert y[4]["rent_in"] > 0 and y[4]["utilities"] == 0 and y[4]["management"] > 0


def test_property_tax_and_common_charges_grow_and_the_mortgage_payment_does_not():
    y = {r["year"]: r for r in plan(_base())["years"]}
    assert y[2]["property_tax"] == pytest.approx(7_000 * 1.03)
    assert y[2]["common_charges"] == pytest.approx(700 * 12 * 1.03)
    assert y[2]["mortgage_payment"] == pytest.approx(y[1]["mortgage_payment"])


def test_principal_paid_over_the_whole_loan_equals_the_loan_and_the_loan_is_gone_at_the_end():
    p = plan(_base(horizon_years=10))
    assert len(p["years"]) == 30
    assert sum(r["principal"] for r in p["years"]) == pytest.approx(600_000, rel=1e-6)
    assert p["years"][-1]["loan_balance"] == pytest.approx(0, abs=1e-6)
    assert p["summary"]["loan_paid_off_year"] == 30 and p["summary"]["principal_overtakes_interest_year"] is not None


def test_a_cash_purchase_has_no_mortgage_no_recording_tax_and_no_pmi():
    p = plan(_base(down_pct=1.0))
    assert p["loan"] == 0 and p["monthly_year1"]["mortgage_payment"] == 0
    assert p["cash_to_close"]["closing_costs"]["mortgage_recording_tax"] == 0
    assert p["monthly_year1"]["pmi"] == 0 and p["summary"]["loan_paid_off_year"] is None


def test_mortgage_insurance_applies_under_20_percent_down_and_ends_when_the_loan_reaches_80_percent():
    thin = plan(_base(down_pct=0.10))
    assert thin["monthly_year1"]["pmi"] == pytest.approx(0.005 * 720_000 / 12)
    end = thin["summary"]["pmi_ends_year"]
    assert end is not None and thin["years"][end - 1]["pmi"] == 0 and thin["years"][end - 2]["pmi"] > 0
    assert plan(_base(down_pct=0.25))["monthly_year1"]["pmi"] == 0
    assert plan(_base(down_pct=0.10, pmi_annual_pct=0))["monthly_year1"]["pmi"] == 0


def test_custom_costs_are_counted_when_they_fall_due():
    p = plan(_base(custom=[CustomCost("renovation", 30_000, "once", 0), CustomCost("parking", 300, "monthly", 1, 5),
                           CustomCost("assessment", 12_000, "once", 3), CustomCost("storage", 600, "annual", 2)]))
    assert p["cash_to_close"]["your_upfront_costs"] == 30_000
    y = {r["year"]: r for r in p["years"]}
    assert y[1]["your_costs"] == 3_600 and y[2]["your_costs"] == 3_600 + 600
    assert y[3]["your_costs"] == 3_600 + 600 + 12_000 and y[6]["your_costs"] == 600  # parking ended after year 5


def test_selling_nets_value_less_selling_costs_less_the_loan_payoff_and_the_gain_reconciles():
    p = plan(_base(horizon_years=10))
    h = p["years"][9]
    s = p["sale"]
    assert s["home_value"] == pytest.approx(800_000 * 1.02**10)
    assert s["selling_costs"] == pytest.approx(s["home_value"] * 0.08)
    assert s["net_proceeds"] == pytest.approx(s["home_value"] - s["selling_costs"] - h["loan_balance"])
    sm = p["summary"]
    assert sm["net_gain_at_horizon"] == pytest.approx(s["net_proceeds"] - sm["cash_to_close"] - sm["net_out_over_horizon"])
    assert sm["net_out_over_horizon"] == pytest.approx(sum(r["net_out"] for r in p["years"][:10]))


def test_living_in_it_counts_the_rent_you_avoid_so_it_can_be_compared_with_renting():
    live = plan(_base(horizon_years=5))
    avoided = sum(4_000 * 12 * 1.03 ** (y - 1) for y in range(1, 6))
    assert live["summary"]["rent_avoided_over_horizon"] == pytest.approx(avoided)
    assert live["summary"]["net_gain_vs_renting"] == pytest.approx(live["summary"]["net_gain_at_horizon"] + avoided)
    assert plan(_base(phases=[{"from_year": 1, "share_rented": 1.0}]))["summary"]["rent_avoided_over_horizon"] == 0
    hack = plan(_base(horizon_years=1, phases=[{"from_year": 1, "share_rented": 1 / 3}]))
    assert hack["summary"]["rent_avoided_over_horizon"] == pytest.approx(4_000 * 12 * 2 / 3)  # only the part you live in


def test_the_horizon_can_extend_past_the_loan_and_costs_continue_without_a_payment():
    p = plan(_base(term_years=15, horizon_years=20))
    assert len(p["years"]) == 20 and p["years"][16]["mortgage_payment"] == 0 and p["years"][16]["property_tax"] > 0


# ------------------------------------------------------------------ parity with the artifact's JavaScript

import json  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
from dataclasses import asdict  # noqa: E402
from pathlib import Path  # noqa: E402

ARTIFACT = Path(__file__).resolve().parents[2] / "docs" / "artifact" / "staging.html"
NODE = shutil.which("node") or str(Path.home() / ".local/node/bin/node")

CASES = {
    "live": dict(price=800_000, tax_annual=7_000, common_monthly=700, rent_monthly=4_000, utilities_monthly=180),
    "rent all": dict(price=1_250_000, down_pct=0.30, rate=0.0695, tax_annual=11_000, common_monthly=900, rent_monthly=6_500,
                     management_pct=0.05, phases=[{"from_year": 1, "share_rented": 1.0}], horizon_years=15),
    "house hack": dict(price=900_000, down_pct=0.10, tax_annual=8_000, common_monthly=650, rent_monthly=5_000,
                       utilities_monthly=220, phases=[{"from_year": 1, "share_rented": 1 / 3}], appreciation=0.035),
    "live then rent": dict(price=2_400_000, down_pct=0.20, tax_annual=20_000, common_monthly=1_500, rent_monthly=9_000,
                           management_pct=0.06, phases=[{"from_year": 1, "share_rented": 0.0}, {"from_year": 6, "share_rented": 1.0}],
                           horizon_years=12, new_development=True),
    "cash purchase": dict(price=500_000, down_pct=1.0, tax_annual=4_000, common_monthly=400, rent_monthly=2_600),
    "custom costs + short loan": dict(price=700_000, term_years=15, horizon_years=20, tax_annual=6_000, common_monthly=500, rent_monthly=3_500,
                                       custom=[CustomCost("renovation", 30_000, "once", 0), CustomCost("parking", 300, "monthly", 1, 5),
                                               CustomCost("assessment", 12_000, "once", 3), CustomCost("storage", 600, "annual", 2)]),
}


def _close(a, b, path=""):
    if isinstance(a, dict):
        assert set(a) == set(b), f"{path}: keys differ {set(a) ^ set(b)}"
        for k in a:
            _close(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list):
        assert len(a) == len(b), path
        for n, (x, y) in enumerate(zip(a, b, strict=True)):
            _close(x, y, f"{path}[{n}]")
    elif isinstance(a, (int, float)) and not isinstance(a, bool):
        assert b == pytest.approx(a, rel=1e-9, abs=1e-6), f"{path}: python {a} vs javascript {b}"
    else:
        assert a == b, f"{path}: {a!r} vs {b!r}"


@pytest.mark.skipif(not Path(NODE).exists(), reason="node is not installed")
def test_the_artifacts_javascript_gives_the_same_numbers_as_the_backend():
    html = ARTIFACT.read_text()
    js = html.split("/*PURCHASE-START*/")[1].split("/*PURCHASE-END*/")[0]
    payload = {name: {**kw, "custom": [asdict(c) for c in kw.get("custom", [])]} for name, kw in CASES.items()}
    script = js + "\nconst cases=" + json.dumps(payload) + ";const out={};for(const k in cases)out[k]=purchasePlan(cases[k]);console.log(JSON.stringify(out));"
    out = json.loads(subprocess.run([NODE, "-e", script], capture_output=True, text=True, check=True).stdout)
    for name, kw in CASES.items():
        expected = plan(PurchaseInputs(**kw))
        # JS omits absent optionals as null; normalise Python None the same way (json round trip)
        _close(json.loads(json.dumps(expected)), out[name], name)
