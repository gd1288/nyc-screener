"""Plain-number summaries of the stored macro series (see app/sources/fred.py), for display and calibration.

No modelling here: it reports what the series did. The stress scenarios use it as a reality check
(how severe were New York's real price drawdowns), and the UI shows the rate context beside the
mortgage-rate input.
"""


def latest(points: list[list]) -> tuple[str, float] | None:
    return (points[-1][0], points[-1][1]) if points else None


def max_drawdown(points: list[list]) -> dict | None:
    """Largest peak-to-trough fall in an index series, and how long it took to get back.

    `points` is [[iso_date, value], ...] oldest first. Returns None when the series never falls.
    Recovery is the first later point at or above the prior peak (None if it has not recovered).
    """
    if len(points) < 2:
        return None
    peak_i = 0
    best = None  # (drawdown, peak_i, trough_i)
    for i, (_, v) in enumerate(points):
        if v > points[peak_i][1]:
            peak_i = i
        dd = v / points[peak_i][1] - 1
        if best is None or dd < best[0]:
            best = (dd, peak_i, i)
    if best is None or best[0] >= 0:
        return None
    dd, pi, ti = best
    peak_value = points[pi][1]
    rec = next((j for j in range(ti + 1, len(points)) if points[j][1] >= peak_value), None)
    return {
        "drawdown": round(dd, 4),
        "peak_date": points[pi][0],
        "trough_date": points[ti][0],
        "recovery_date": points[rec][0] if rec is not None else None,
        "periods_peak_to_trough": ti - pi,
        "periods_trough_to_recovery": (rec - ti) if rec is not None else None,
    }


def summary(macro: dict[str, dict]) -> dict:
    """Everything the UI shows about market context, as plain numbers with dates and citations."""

    def pts(sid):
        return (macro.get(sid) or {}).get("points") or []

    out: dict = {}
    m, t = latest(pts("MORTGAGE30US")), latest(pts("DGS10"))
    if m:
        out["mortgage30"] = {"date": m[0], "rate": round(m[1] / 100, 4)}
    if t:
        out["treasury10"] = {"date": t[0], "rate": round(t[1] / 100, 4)}
    if m and t:
        out["mortgage_spread"] = round((m[1] - t[1]) / 100, 4)
    dd = max_drawdown(pts("ATNHPIUS35614Q"))
    if dd:
        out["nyc_drawdown"] = {**dd, "series": "ATNHPIUS35614Q", "frequency": "quarterly"}
    out["citations"] = {sid: macro[sid].get("citation", "") for sid in macro}
    return out
