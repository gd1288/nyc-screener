"""FHFA tract HPI: row filtering and the growth math derived from it."""

import pytest

from app.sources import fhfa_hpi


def rows(*triples):
    return [{"tract": t, "state_abbr": "TX", "year": str(y), "hpi": h} for t, y, h in triples]


def test_only_loaded_tracts_inside_the_year_window_are_kept():
    """The file is ~8M national tract-years; peak memory has to be set by the tracts we loaded,
    not by the file."""
    collected = fhfa_hpi.collect_index(
        rows(("48453000100", 2020, "100"), ("48453000100", 2005, "60"), ("99999999999", 2020, "100")),
        wanted={"48453000100"},
        min_year=2011,
    )
    assert collected == {"48453000100": {2020: 100.0}}


@pytest.mark.parametrize("value", ["", " ", "n/a", None, "0"])
def test_blank_suppressed_and_zero_index_values_are_skipped(value):
    """FHFA publishes suppressed tract-years as blanks; a zero index would divide into infinity."""
    assert fhfa_hpi.collect_index(rows(("48453000100", 2020, value)), {"48453000100"}, 2011) == {}


def test_a_row_missing_the_year_or_index_column_does_not_abort_the_stream():
    collected = fhfa_hpi.collect_index(
        [{"tract": "48453000100"}, *rows(("48453000100", 2020, "100"))], {"48453000100"}, 2011
    )
    assert collected == {"48453000100": {2020: 100.0}}


def test_cagr_is_compound_growth_between_the_latest_year_and_its_baseline():
    """Hand-worked: an index doubling over 10 years is 2**(1/10)-1 = 7.177% a year."""
    result = fhfa_hpi.compute_cagrs({"48453000100": {2015: 100.0, 2025: 200.0}})
    assert result["hpi_cagr_10y"]["48453000100"] == pytest.approx(0.071773, abs=1e-6)
    assert "48453000100" not in result["hpi_cagr_5y"]  # no 2020 observation to measure from


def test_a_missing_baseline_year_produces_no_metric_rather_than_an_interpolated_one():
    """Interpolating across a gap would invent an index value and report it with the same
    confidence as a measured one."""
    result = fhfa_hpi.compute_cagrs({"t": {2014: 100.0, 2025: 200.0}})
    assert "t" not in result["hpi_cagr_10y"]
    assert "t" not in result["hpi_cagr_5y"]


def test_the_latest_year_is_per_tract_not_global():
    """A tract whose data stops early must be measured from its own latest year, not from the
    newest year anywhere in the file - otherwise its baseline silently shifts."""
    result = fhfa_hpi.compute_cagrs({"fresh": {2015: 100.0, 2025: 200.0}, "stale": {2010: 100.0, 2020: 150.0}})
    assert result["hpi_cagr_10y"]["stale"] == pytest.approx(0.041380, abs=1e-6)


def test_annual_change_uses_the_prior_year():
    result = fhfa_hpi.compute_cagrs({"t": {2024: 100.0, 2025: 110.0}})
    assert result["hpi_annual_change"]["t"] == pytest.approx(0.1)


def test_a_declining_market_reports_a_negative_cagr():
    result = fhfa_hpi.compute_cagrs({"t": {2020: 200.0, 2025: 100.0}})
    assert result["hpi_cagr_5y"]["t"] == pytest.approx(2**-0.2 - 1, abs=1e-6)
    assert result["hpi_cagr_5y"]["t"] < 0


def test_source_is_tagged_national_and_tract_level():
    """A national source that inherits the NYC-only defaults would be skipped for every other
    region, silently."""
    source = fhfa_hpi.FhfaTractHpi("fhfa_tract_hpi")
    assert (source.coverage, source.granularity) == ("national", "tract")
