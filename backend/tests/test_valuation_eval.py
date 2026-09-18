from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Sale
from app.valuation import comps
from app.valuation import eval as valuation_eval

AS_OF = date(2026, 1, 1)


def make_session():
    engine_ = create_engine("sqlite://")
    Base.metadata.create_all(engine_)
    return sessionmaker(bind=engine_)()


def add_sale(session, *, days_before: int, price: float, address="10 WILLIAM ST", building="1-00123", unit=None):
    session.add(
        Sale(
            bbl=f"1{building.split('-')[1]}{(unit or '0001')[-4:]}",
            building_key=building,
            address=address,
            unit=unit,
            price=price,
            sale_date=AS_OF - timedelta(days=days_before),
            category="13 CONDOS - ELEVATOR APARTMENTS",
            source="test",
        )
    )


def test_comp_set_never_includes_the_target_sale_or_later(monkeypatch):
    """The one assertion that makes the headline error number mean anything.

    Every graded prediction must be built only from sales that had already closed. A comp set
    contaminated with the target sale (or anything after it) yields a flattering median that looks
    exactly like a correct one, so this checks the comp sets directly instead of trusting the query.
    """
    session = make_session()
    # Ascending, distinct prices: a leaked comp is identifiable by value alone.
    for i, days in enumerate([900, 800, 700, 600, 500, 400, 300, 200, 100]):
        add_sale(session, days_before=days, price=100_000 * (i + 1), unit=f"{i:04d}")
    session.commit()

    seen: list[list[float]] = []
    original = comps.from_building_sales
    monkeypatch.setattr(comps, "from_building_sales", lambda prices: seen.append(list(prices)) or original(prices))

    valuation_eval.run_eval(session, as_of=AS_OF, months=12)

    assert seen, "expected at least one scored sale"
    scored = [(s.sale_date, s.price) for s in session.query(Sale).order_by(Sale.sale_date)]
    for comp_prices in seen:
        # Find the target this comp set belongs to: its comps are strictly cheaper here, so the
        # target is the next price up. Assert no comp is from the target's date or later.
        newest_comp = max(comp_prices)
        target_price = newest_comp + 100_000
        target_date = next(d for d, p in scored if p == target_price)
        comp_dates = [d for d, p in scored if p in comp_prices]
        assert all(d < target_date for d in comp_dates), f"leaked a comp at/after {target_date}"
        assert target_price not in comp_prices, "target sale leaked into its own comp set"


def test_same_day_sales_are_excluded_from_each_others_comps():
    """A sale that closed the same day is not information you had when pricing this one."""
    session = make_session()
    for i in range(3):
        add_sale(session, days_before=400 + i, price=500_000, unit=f"{i:04d}")
    # Two sales on one day: neither may use the other, so neither reaches the 3-comp minimum
    # from the 3 older sales alone... it does (3 priors), but the same-day peer must not be a 4th.
    add_sale(session, days_before=100, price=900_000, unit="8888")
    add_sale(session, days_before=100, price=910_000, unit="9999")
    session.commit()

    result = valuation_eval.run_eval(session, as_of=AS_OF, months=12)

    # Both same-day sales are scored against the same 3 older comps (median 500k), never each other.
    assert result.n_scored == 2
    expected = (abs(500_000 - 900_000) / 900_000 + abs(500_000 - 910_000) / 910_000) / 2
    assert result.median_abs_pct_error == pytest.approx(expected, abs=1e-6)


def test_error_is_the_building_median_against_the_actual_price():
    """Hand-worked: comps of 400k/500k/600k predict 500k; a sale at 400k is 25% off."""
    session = make_session()
    for i, price in enumerate([400_000, 500_000, 600_000]):
        add_sale(session, days_before=500 + i, price=price, unit=f"{i:04d}")
    add_sale(session, days_before=100, price=400_000, unit="7777")
    session.commit()

    result = valuation_eval.run_eval(session, as_of=AS_OF, months=12)

    assert result.n_scored == 1
    assert result.median_abs_pct_error == pytest.approx(0.25)


def test_a_sale_without_enough_comps_is_counted_but_not_scored():
    """Coverage has to stay visible: silently dropping unscoreable sales would let the median be
    computed over a shrinking, easier subset without anything saying so."""
    session = make_session()
    add_sale(session, days_before=500, price=500_000, unit="0001")
    add_sale(session, days_before=100, price=800_000, unit="0002")
    session.commit()

    result = valuation_eval.run_eval(session, as_of=AS_OF, months=12)

    assert result.n_candidates == 1  # only the recent sale is in the 12-month window
    assert result.n_scored == 0
    assert result.median_abs_pct_error is None
    assert result.coverage == 0.0


def test_sales_in_a_different_building_are_not_comps():
    session = make_session()
    for i in range(5):
        add_sale(
            session, days_before=500 + i, price=500_000, building="1-00999", address="99 OTHER ST", unit=f"{i:04d}"
        )
    add_sale(session, days_before=100, price=800_000, unit="0002")
    session.commit()

    assert valuation_eval.run_eval(session, as_of=AS_OF, months=12).n_scored == 0


def test_same_block_but_a_different_street_address_is_not_the_same_building():
    """`building_key` is the tax block, which two separate condos can share - the normalised street
    address is what separates them."""
    session = make_session()
    for i in range(4):
        add_sale(session, days_before=500 + i, price=500_000, address="12 WILLIAM STREET", unit=f"{i:04d}")
    add_sale(session, days_before=100, price=800_000, address="10 WILLIAM ST", unit="0002")
    session.commit()

    assert valuation_eval.run_eval(session, as_of=AS_OF, months=12).n_scored == 0


def test_comps_older_than_the_window_are_dropped():
    session = make_session()
    for i in range(3):
        add_sale(session, days_before=365 * 4 + i, price=500_000, unit=f"{i:04d}")
    add_sale(session, days_before=100, price=800_000, unit="0002")
    session.commit()

    assert valuation_eval.run_eval(session, as_of=AS_OF, months=12, comps_years=3).n_scored == 0


def _result(error: float | None) -> valuation_eval.EvalResult:
    return valuation_eval.EvalResult(
        median_abs_pct_error=error,
        n_scored=10,
        n_candidates=10,
        coverage=1.0,
        config={"comps_rules_version": valuation_eval.COMPS_RULES_VERSION},
    )


def test_baseline_gate_blocks_a_regression_and_allows_an_improvement():
    baseline = _result(0.20).to_json()
    assert valuation_eval.check_against_baseline(_result(0.25), baseline)[0] is False
    assert valuation_eval.check_against_baseline(_result(0.15), baseline)[0] is True
    assert valuation_eval.check_against_baseline(_result(0.203), baseline)[0] is True  # within tolerance


def test_baseline_gate_does_not_compare_across_comps_rules_versions():
    """A baseline written under different comps rules isn't a like-for-like comparison, so it asks
    for a new one rather than passing or failing a number that no longer means the same thing."""
    stale = {"median_abs_pct_error": 0.05, "config": {"comps_rules_version": valuation_eval.COMPS_RULES_VERSION - 1}}
    ok, message = valuation_eval.check_against_baseline(_result(0.30), stale)
    assert ok is True
    assert "record a new baseline" in message


def test_an_eval_that_scored_nothing_cannot_pass_the_gate():
    ok, _ = valuation_eval.check_against_baseline(_result(None), _result(0.20).to_json())
    assert ok is False
