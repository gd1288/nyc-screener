"""FRED macro series: parsing, storage, key hygiene, and the interest_rate factor it backs."""

import logging
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import AppSetting
from app.services import MarketContext
from app.sources.base import SourceContext
from app.sources.fred import FredSeries, parse_observations
from app.valuation.factors import PropertyProfile, market_estimate

KEY = "k3y-should-never-appear-in-errors"


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as s:
        yield s


class _Resp:
    def __init__(self, payload, status=200):
        self.payload, self.status_code = payload, status

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            req = httpx.Request("GET", f"https://api.stlouisfed.org/fred/series/observations?api_key={KEY}")
            raise httpx.HTTPStatusError(f"Client error for url {req.url}", request=req, response=httpx.Response(self.status_code, request=req))


class _Http:
    def __init__(self, payload=None, status=200):
        self.payload, self.status, self.calls = payload, status, []

    def get(self, url, params=None, timeout=None):
        self.calls.append(params)
        return _Resp(self.payload, self.status)


def _payload(n=30, start=6.0):
    obs = [{"date": f"2026-{1 + i // 4:02d}-{1 + (i % 4) * 7:02d}", "value": f"{start + i * 0.01:.2f}"} for i in range(n)]
    obs.insert(3, {"date": "2026-01-29", "value": "."})  # FRED's marker for a missing week
    return {"observations": obs}


def _ctx(session, http, key=KEY):
    return SourceContext(session=session, settings=SimpleNamespace(fred_api_key=key), http=http)


def test_missing_values_are_dropped_not_zeroed():
    pts = parse_observations({"observations": [{"date": "2026-01-01", "value": "6.5"}, {"date": "2026-01-08", "value": "."}, {"date": "2026-01-15"}]})
    assert pts == [["2026-01-01", 6.5]]


def test_run_stores_series_with_attribution(session):
    http = _Http(_payload())
    n = FredSeries("fred_series").run(_ctx(session, http))
    stored = session.get(AppSetting, "macro:MORTGAGE30US").value
    assert len(stored["points"]) == 30 and n == 30 * 3  # three series, the fake returns 30 points for each
    assert "not endorsed or certified by the Federal Reserve Bank of St. Louis" in stored["notice"]
    assert "Freddie Mac" in stored["citation"]
    assert len(http.calls) == 3  # exactly one request per series per run


def test_http_errors_never_leak_the_api_key(session):
    with pytest.raises(RuntimeError) as e:
        FredSeries("fred_series").run(_ctx(session, _Http({}, status=401)))
    assert KEY not in str(e.value) and "401" in str(e.value)


def test_empty_response_is_an_error_not_a_silent_success(session):
    with pytest.raises(RuntimeError, match="no observations"):
        FredSeries("fred_series").run(_ctx(session, _Http({"observations": []})))


def test_probe_is_not_run_without_a_key(session):
    ok, detail = FredSeries("fred_series").probe(_ctx(session, _Http(), key=""))
    assert ok is None and "FRED_API_KEY" in detail


def test_source_is_skipped_until_a_key_is_configured():
    assert FredSeries("fred_series").missing_requirements(SimpleNamespace(fred_api_key="")) == ["fred_api_key"]


def _market(points):
    macro = {"MORTGAGE30US": {"points": points}} if points is not None else {}
    return MarketContext(names={}, scores={}, metrics={}, city_value_cagr_10y=None, listing_ppsf_by_nta={}, macro=macro)


def test_interest_rate_factor_uses_latest_reading_and_history_range():
    points = parse_observations(_payload())
    est = market_estimate(_market(points), PropertyProfile(price=1_000_000))["interest_rate"]
    assert est.value == round(points[-1][1] / 100, 4)
    assert est.p10 < est.value or est.p10 == est.value
    assert est.p10 <= est.p90 and est.as_of == points[-1][0]
    assert "FRED" in est.source and "investor" in est.source


@pytest.mark.parametrize("points", [None, [["2026-01-01", 6.5]] * 5])
def test_interest_rate_stays_a_gap_without_enough_data(points):
    """No key, no fetch, or a stub history must fall back to the fixed default, not invent a range."""
    assert market_estimate(_market(points), PropertyProfile(price=1_000_000))["interest_rate"] is None


def test_market_context_loads_stored_series(session):
    FredSeries("fred_series").run(_ctx(session, _Http(_payload())))
    assert len(MarketContext.load(session).macro["MORTGAGE30US"]["points"]) == 30


def test_request_logging_never_prints_the_api_key(caplog):
    """httpx logs the full URL at INFO; the filter installed by the FRED module must redact the key."""
    with caplog.at_level(logging.INFO, logger="httpx"):
        logging.getLogger("httpx").info('HTTP Request: %s %s "%s"', "GET", f"https://api.stlouisfed.org/x?api_key={KEY}&file_type=json", "HTTP/1.1 200 OK")
    text = " ".join(r.getMessage() for r in caplog.records)
    assert KEY not in text and "api_key=REDACTED" in text and "file_type=json" in text


# ------------------------------------------------------------------ macro summaries

from app.valuation import macro as mac  # noqa: E402


def test_max_drawdown_finds_peak_trough_and_recovery():
    pts = [["q1", 100], ["q2", 120], ["q3", 96], ["q4", 90], ["q5", 110], ["q6", 121]]
    dd = mac.max_drawdown(pts)
    assert dd["drawdown"] == round(90 / 120 - 1, 4)
    assert (dd["peak_date"], dd["trough_date"], dd["recovery_date"]) == ("q2", "q4", "q6")
    assert dd["periods_peak_to_trough"] == 2 and dd["periods_trough_to_recovery"] == 2


def test_drawdown_that_never_recovers_says_so():
    dd = mac.max_drawdown([["a", 100], ["b", 80], ["c", 85]])
    assert dd["recovery_date"] is None and dd["periods_trough_to_recovery"] is None


def test_a_series_that_only_rises_has_no_drawdown():
    assert mac.max_drawdown([["a", 1], ["b", 2], ["c", 3]]) is None and mac.max_drawdown([["a", 1]]) is None


def test_summary_reports_rates_spread_and_citations_without_inventing_missing_series():
    macro = {
        "MORTGAGE30US": {"points": [["2026-09-10", 6.90], ["2026-09-17", 6.95]], "citation": "Freddie Mac..."},
        "DGS10": {"points": [["2026-09-16", 5.01]], "citation": "Board of Governors..."},
    }
    s = mac.summary(macro)
    assert s["mortgage30"] == {"date": "2026-09-17", "rate": 0.0695}
    assert s["treasury10"]["rate"] == 0.0501 and s["mortgage_spread"] == 0.0194
    assert "nyc_drawdown" not in s and set(s["citations"]) == {"MORTGAGE30US", "DGS10"}
    assert mac.summary({}) == {"citations": {}}
