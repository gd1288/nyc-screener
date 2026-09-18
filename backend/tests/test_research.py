"""Series evaluation and the research registry.

The statistics tests matter more than they look: this module's whole job is to stop a source being
adopted on evidence that isn't there, so the cases below are mostly about what it *refuses* to claim.
"""

import json
from datetime import date, timedelta

import pytest

from app.research import evaluate_series as ev
from app.research import registry as reg

# ------------------------------------------------------------------ series evaluation


def test_growth_conversion_skips_non_consecutive_periods():
    """Bridging a gap would invent a one-year change out of a three-year interval."""
    assert ev.to_growth({2020: 100.0, 2021: 110.0, 2025: 200.0}) == {2021: pytest.approx(0.1)}


def test_growth_conversion_ignores_a_zero_base():
    assert ev.to_growth({2020: 0.0, 2021: 110.0}) == {}


def test_two_rising_series_are_not_reported_as_correlated_just_for_rising():
    """The trap this module exists to avoid. Two unrelated series that both trend upward correlate
    near 1.0 on levels; on growth they do not. If this ever fails, every correlation the research
    agent reports becomes meaningless."""
    candidate = {y: 100.0 * (1.05 ** (y - 2000)) for y in range(2000, 2025)}  # smooth 5% growth
    target = {y: 50.0 + (y - 2000) * 3 + ((y % 3) - 1) * 9 for y in range(2000, 2025)}  # rising, jagged

    result = ev.evaluate(candidate, target, "target")

    # Growth of a constant-rate series has zero variance, so no correlation is even computable.
    assert result.best_pearson is None or abs(result.best_pearson) < 0.5
    assert not result.significant


def test_a_perfect_lagged_relationship_is_found_at_the_right_lag():
    """Positive lag means the candidate moves first."""
    target_growth = {y: 0.05 + 0.02 * ((y % 5) - 2) for y in range(2000, 2030)}
    candidate_growth = {y: target_growth[y + 2] for y in range(2000, 2028)}  # candidate leads by 2

    result = ev.evaluate(candidate_growth, target_growth, "hpi", candidate_is_growth=True, target_is_growth=True)

    assert result.best_lag == 2
    assert result.best_pearson == pytest.approx(1.0, abs=1e-6)
    assert result.significant is True


def test_a_contemporaneous_match_is_flagged_as_not_a_leading_indicator():
    """Moving *with* the target is not the same as predicting it, and a source adopted on a lag-0
    correlation would add nothing a later reading of the target wouldn't."""
    growth = {y: 0.04 + 0.03 * ((y % 7) - 3) for y in range(2000, 2030)}

    result = ev.evaluate(growth, growth, "hpi", candidate_is_growth=True, target_is_growth=True)

    assert result.best_lag == 0
    assert any("not a leading indicator" in w for w in result.warnings)


def test_a_small_sample_is_reported_as_indicative_not_significant():
    """A correlation of ~1.0 on six points is not evidence, and `significant` must say so."""
    growth = {y: 0.05 + 0.01 * (y % 3) for y in range(2000, 2008)}

    result = ev.evaluate(growth, growth, "hpi", candidate_is_growth=True, target_is_growth=True)

    assert result.n_observations < ev.SMALL_SAMPLE
    assert result.significant is False
    assert any("indicative" in w for w in result.warnings)


def test_a_noisy_unrelated_series_reports_a_confidence_interval_spanning_zero():
    import numpy as np

    rng = np.random.default_rng(7)
    candidate = {y: float(rng.normal()) for y in range(2000, 2030)}
    target = {y: float(rng.normal()) for y in range(2000, 2030)}

    result = ev.evaluate(candidate, target, "hpi", candidate_is_growth=True, target_is_growth=True)

    assert result.significant is False
    assert any("includes zero" in w for w in result.warnings)


def test_too_few_periods_raises_rather_than_returning_a_confident_number():
    with pytest.raises(ev.NotEnoughData):
        ev.evaluate({2020: 1.0, 2021: 2.0}, {2020: 1.0, 2021: 2.0}, "hpi")


def test_a_flat_series_yields_no_correlation_rather_than_a_divide_by_zero():
    flat = dict.fromkeys(range(2000, 2030), 0.03)
    varying = {y: 0.02 + 0.01 * (y % 4) for y in range(2000, 2030)}

    result = ev.evaluate(flat, varying, "hpi", candidate_is_growth=True, target_is_growth=True)

    assert result.best_pearson is None
    assert result.significant is False


def test_spearman_survives_an_outlier_that_breaks_pearson():
    """Rank correlation is reported precisely so one crisis year can't decide the verdict."""
    candidate = {y: float(y) for y in range(2000, 2030)}
    target = {y: float(y) for y in range(2000, 2030)}
    target[2029] = -500.0  # one catastrophic year

    result = ev.evaluate(candidate, target, "hpi", candidate_is_growth=True, target_is_growth=True)

    assert result.best_spearman is not None
    assert abs(result.best_spearman) > abs(result.best_pearson or 0)


# ------------------------------------------------------------------ registry


def _entry(slug="src", status=reg.PROPOSED, decided_at="2026-01-01"):
    return reg.RegistryEntry(slug=slug, name="A source", status=status, decided_at=decided_at)


def test_registry_round_trips(tmp_path):
    path = tmp_path / "registry.json"
    reg.record(_entry(status=reg.APPROVED), path)
    loaded = reg.load(path)
    assert [(e.slug, e.status) for e in loaded] == [("src", reg.APPROVED)]
    assert json.loads(path.read_text())["version"] == reg.VERSION


def test_recording_the_same_slug_twice_replaces_rather_than_stacks(tmp_path):
    path = tmp_path / "registry.json"
    reg.record(_entry(status=reg.PROPOSED), path)
    reg.record(_entry(status=reg.REJECTED, decided_at="2026-06-01"), path)
    entries = reg.load(path)
    assert len(entries) == 1
    assert entries[0].status == reg.REJECTED


def test_an_unknown_status_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        reg.record(_entry(status="maybe"), tmp_path / "r.json")


def test_an_approved_source_is_skipped_permanently():
    skip, why = reg.should_skip("src", [_entry(status=reg.APPROVED)], today=date(2030, 1, 1))
    assert skip is True
    assert "approved" in why


def test_a_rejected_source_is_skipped_during_the_cooldown_and_allowed_after():
    decided = date(2026, 1, 1)
    entries = [_entry(status=reg.REJECTED, decided_at=decided.isoformat())]

    during, why_during = reg.should_skip("src", entries, today=decided + timedelta(days=30))
    after, why_after = reg.should_skip("src", entries, today=decided + timedelta(days=91))

    assert during is True
    assert "eligible again" in why_during
    assert after is False
    assert "cooldown has passed" in why_after


def test_an_unknown_slug_is_not_skipped():
    assert reg.should_skip("brand-new", [_entry()]) == (False, "")


def test_a_skip_always_explains_itself():
    """A silently skipped candidate looks to the user like the agent failed to find it."""
    for status in (reg.APPROVED, reg.IMPLEMENTED, reg.REJECTED):
        skip, why = reg.should_skip("src", [_entry(status=status)], today=date(2026, 1, 2))
        assert skip is True and why


def test_precision_counts_only_decided_candidates():
    """An undecided proposal is not evidence the agent did badly."""
    entries = [
        _entry("a", reg.APPROVED),
        _entry("b", reg.IMPLEMENTED),
        _entry("c", reg.REJECTED),
        _entry("d", reg.PROPOSED),
    ]
    assert reg.precision(entries) == {"proposed": 4, "decided": 3, "approved": 2, "precision": 0.6667}


def test_precision_is_none_before_anything_is_decided():
    assert reg.precision([_entry()])["precision"] is None


def test_the_shipped_registry_file_is_valid():
    """The repo's own registry.json must stay loadable — the skill reads it before every run."""
    assert isinstance(reg.load(), list)


# ------------------------------------------------------------------ criteria ledger

from app.research import criteria as crit  # noqa: E402

FACTORS = {"rent_growth", "vacancy_pct"}


def _crit(**kw):
    return {"id": "x", "label": "X", "status": "idea", **kw}


def test_the_committed_ledger_is_valid():
    from app.valuation.factors import FACTOR_DEFS

    assert crit.validate(crit.load(), {f.key for f in FACTOR_DEFS}) == []


def test_ledger_rejects_unknown_status_duplicates_and_undated_decisions():
    problems = crit.validate(
        [_crit(status="maybe"), _crit(), _crit(id="y", status="approved"), _crit(id="z", status="rejected", decided="2026-09-18")],
        FACTORS,
    )
    text = " | ".join(problems)
    assert "unknown status 'maybe'" in text
    assert "duplicate id" in text
    assert "approved' needs a 'decided'" in text
    assert "rejected needs a 'reason'" in text


def test_live_entry_must_point_at_a_real_factor():
    bad = crit.validate([_crit(status="live", decided="2026-09-18", factor="nope")], FACTORS)
    ok = crit.validate([_crit(status="live", decided="2026-09-18", factor="rent_growth")], FACTORS)
    assert any("not in valuation/factors.py" in p for p in bad)
    assert ok == []


def test_ui_suggestions_may_only_target_staging():
    good = _crit(ui_suggestion={"target": "staging", "description": "add a dial"})
    bad_target = _crit(ui_suggestion={"target": "main", "description": "add a dial"})
    assert crit.validate([good], FACTORS) == []
    assert crit.validate([bad_target], FACTORS)
