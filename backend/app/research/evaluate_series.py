"""Does a candidate data series actually predict what we care about?

The research agent proposes free data sources. This is the deterministic half of judging one: it
measures how strongly a candidate series moves with home-price or rent growth, and whether it moves
*first*. Deliberately code, not model judgement — a correlation is arithmetic, and computing it here
means the agent spends its budget on finding sources rather than on estimating numbers it cannot.

Three decisions here exist because the naive version of this function is badly misleading:

1. **Levels are differenced before correlating.** Two series that both trend upward correlate near
   1.0 no matter what they measure — mortgage rates against house prices, or ice-cream sales against
   drownings. `to_growth()` converts to period-over-period change first, and `evaluate()` refuses a
   level series unless the caller has said it is already a growth rate.
2. **Spearman is reported next to Pearson.** Pearson assumes a linear relationship and a handful of
   crisis years can manufacture or destroy one; rank correlation survives that.
3. **A confidence interval is always attached.** These series are annual, so a decade of history is
   ~10 points. A correlation of 0.6 on n=10 is indistinguishable from noise, and reporting it bare
   invites a source being adopted on evidence that does not exist.
"""

import math
from dataclasses import asdict, dataclass, field

import numpy as np

MIN_OBSERVATIONS = 5  # below this a correlation is arithmetic, not evidence
SMALL_SAMPLE = 20
DEFAULT_MAX_LAG = 3


class NotEnoughData(ValueError):
    pass


def to_growth(series: dict[int, float]) -> dict[int, float]:
    """Level series -> period-over-period growth. Periods must be consecutive to be comparable, so a
    gap ends the run rather than being bridged."""
    periods = sorted(series)
    growth = {}
    for previous, current in zip(periods, periods[1:], strict=False):
        if current - previous == 1 and series[previous]:
            growth[current] = series[current] / series[previous] - 1
    return growth


def _align(candidate: dict[int, float], target: dict[int, float], lag: int) -> tuple[np.ndarray, np.ndarray]:
    """Pair candidate[t] with target[t + lag]. A positive lag means the candidate moves first."""
    periods = sorted(set(candidate) & {t - lag for t in target})
    return (
        np.array([candidate[t] for t in periods], dtype=float),
        np.array([target[t + lag] for t in periods], dtype=float),
    )


def _is_constant(values: np.ndarray) -> bool:
    """`np.std(v) == 0` is not safe here: summing thirty copies of 0.03 leaves a residue around
    1e-18, so an exactly-flat series tests as varying and gets a meaningless correlation of 0.0
    instead of `None`."""
    return bool(np.allclose(values, values[0]))


def _pearson(x: np.ndarray, y: np.ndarray) -> float | None:
    if len(x) < 2 or _is_constant(x) or _is_constant(y):
        return None
    return float(np.corrcoef(x, y)[0, 1])


def _rank(values: np.ndarray) -> np.ndarray:
    """Average ranks, so ties don't bias the rank correlation."""
    order = values.argsort()
    ranks = np.empty(len(values), dtype=float)
    ranks[order] = np.arange(len(values), dtype=float)
    for value in np.unique(values):
        mask = values == value
        if mask.sum() > 1:
            ranks[mask] = ranks[mask].mean()
    return ranks


def _spearman(x: np.ndarray, y: np.ndarray) -> float | None:
    return _pearson(_rank(x), _rank(y)) if len(x) >= 2 else None


def _confidence_interval(r: float | None, n: int) -> tuple[float, float] | None:
    """95% CI via the Fisher z-transformation. Needs no t-table, and an interval that straddles zero
    is the plainest possible statement that the correlation is not evidence of anything."""
    if r is None or n < 4:
        return None
    # atanh(±1) is infinite, so the transformation can't be applied. A perfect correlation is not
    # "unknown" though — returning None would make it fail the excludes-zero check and be reported
    # as insignificant, which is the opposite of what the data says.
    if abs(r) >= 1:
        return (round(r, 4), round(r, 4))
    z = math.atanh(r)
    margin = 1.96 / math.sqrt(n - 3)
    return round(math.tanh(z - margin), 4), round(math.tanh(z + margin), 4)


@dataclass
class LagResult:
    lag: int
    n: int
    pearson: float | None
    spearman: float | None
    confidence_interval: tuple[float, float] | None

    @property
    def excludes_zero(self) -> bool:
        ci = self.confidence_interval
        return ci is not None and (ci[0] > 0 or ci[1] < 0)


@dataclass
class SeriesEvaluation:
    target: str
    best_lag: int | None
    best_pearson: float | None
    best_spearman: float | None
    n_observations: int
    significant: bool
    warnings: list[str] = field(default_factory=list)
    by_lag: list[dict] = field(default_factory=list)

    def to_json(self) -> dict:
        return asdict(self)


def evaluate(
    candidate: dict[int, float],
    target: dict[int, float],
    target_name: str,
    candidate_is_growth: bool = False,
    target_is_growth: bool = False,
    max_lag: int = DEFAULT_MAX_LAG,
) -> SeriesEvaluation:
    """Correlate a candidate series against a target across lags, and say how much to trust it.

    Both series are keyed by period (year, or month index) and differenced to growth unless the
    caller declares them already differenced — correlating two trending levels is the single
    easiest way to make an irrelevant series look predictive.
    """
    candidate_growth = candidate if candidate_is_growth else to_growth(candidate)
    target_growth = target if target_is_growth else to_growth(target)
    if len(candidate_growth) < MIN_OBSERVATIONS or len(target_growth) < MIN_OBSERVATIONS:
        raise NotEnoughData(
            f"need at least {MIN_OBSERVATIONS} comparable periods; "
            f"got {len(candidate_growth)} candidate and {len(target_growth)} target"
        )

    results: list[LagResult] = []
    for lag in range(0, max_lag + 1):
        x, y = _align(candidate_growth, target_growth, lag)
        if len(x) < MIN_OBSERVATIONS:
            continue
        pearson = _pearson(x, y)
        results.append(
            LagResult(
                lag=lag,
                n=len(x),
                pearson=None if pearson is None else round(pearson, 4),
                spearman=None if (s := _spearman(x, y)) is None else round(s, 4),
                confidence_interval=_confidence_interval(pearson, len(x)),
            )
        )
    if not results:
        raise NotEnoughData("no lag had enough overlapping periods to correlate")

    # Ranked on Spearman: the question is whether the candidate moves *with* the target, and a
    # monotonic-but-curved relationship is still a usable predictor.
    best = max(results, key=lambda r: abs(r.spearman or 0))
    warnings = []
    if best.n < SMALL_SAMPLE:
        warnings.append(f"only {best.n} observations — treat as indicative, not evidence")
    if not best.excludes_zero:
        warnings.append("95% confidence interval includes zero — consistent with no relationship")
    if best.lag == 0:
        warnings.append("strongest at lag 0 — moves with the target, so it is not a leading indicator")

    return SeriesEvaluation(
        target=target_name,
        best_lag=best.lag,
        best_pearson=best.pearson,
        best_spearman=best.spearman,
        n_observations=best.n,
        significant=best.excludes_zero and best.n >= SMALL_SAMPLE,
        warnings=warnings,
        by_lag=[asdict(r) for r in results],
    )


def metro_hpi_index(session, http, cbsa: str, years: int = 25) -> dict[int, float]:
    """A metro's annual house-price level: the median FHFA tract index across that CBSA's tracts.

    Read from the published file rather than from `area_metrics`, which stores derived CAGRs — a
    scalar per tract, not a series, and so useless for lead/lag. Storing 25 years x thousands of
    tracts as metrics to avoid one streamed read would bloat a table meant for scoring signals.

    Median rather than mean: a few tracts with extreme indexes would otherwise swing the whole
    metro's series. Only years where enough tracts report are kept, so the series isn't anchored by
    a single early tract.

    **Streams the full ~90MB file on every call.** Comparing several metros through this function
    downloads it once per metro. To compare many, collect once for the union of their tracts with
    `fhfa_hpi.collect_index` and split the result by CBSA yourself — and never wire this directly to
    a user-facing button without that, or each click costs a 90MB download.
    """
    from app.models import Area
    from app.sources import fhfa_hpi

    tracts = {code for (code,) in session.query(Area.code).filter(Area.cbsa == cbsa, Area.kind == "tract")}
    if not tracts:
        raise NotEnoughData(f"no tracts loaded for CBSA {cbsa}; run `app.cli add-region` first")

    from datetime import date

    by_tract = fhfa_hpi.collect_index(fhfa_hpi.stream_rows(http), tracts, date.today().year - years)
    by_year: dict[int, list[float]] = {}
    for series in by_tract.values():
        for year, index in series.items():
            by_year.setdefault(year, []).append(index)
    if not by_year:
        raise NotEnoughData(f"no FHFA observations for any tract in CBSA {cbsa}")
    quorum = max(3, 0.1 * max(len(v) for v in by_year.values()))
    return {year: float(np.median(v)) for year, v in sorted(by_year.items()) if len(v) >= quorum}
