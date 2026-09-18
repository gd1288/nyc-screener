"""Command line: `uv run python -m app.cli refresh [source ...]`, `... sources`, `... backtest`,
`... diagnose [--json]`, `... probe-sources`, `... status [--json]`."""

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.db import SessionLocal, init_db
from app.sources.registry import load_sources, run_pipeline

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HEALTH_FILE = PROJECT_ROOT / ".claude" / "state" / "health.json"


def _last_run_per_source(session) -> dict:
    from sqlalchemy import select

    from app.models import SourceRun

    latest = {}
    for run in session.execute(select(SourceRun).order_by(SourceRun.id)).scalars():
        latest[run.source] = run  # later rows overwrite earlier ones -> last by id
    return latest


def _stop_gate_health() -> dict:
    if HEALTH_FILE.exists():
        try:
            return json.loads(HEALTH_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"tests_ok": None, "checked_at": None}


def cmd_diagnose(as_json: bool) -> int:
    """Health snapshot: per-source last-run status, and the cached stop-gate test/type result.
    Runs no checks itself (that's stop-gate.sh's job) — this only reads and reports state, so
    it's cheap enough for a daily scheduled call and for the `debug` skill to shell out to."""
    entries = load_sources()
    with SessionLocal() as session:
        last_runs = _last_run_per_source(session)

    sources_report = []
    failing = 0
    for e in entries:
        run = last_runs.get(e.name)
        if run is None:
            status, message, finished_at = "never_run", None, None
        else:
            status, message, finished_at = (
                run.status,
                run.message,
                run.finished_at.isoformat() if run.finished_at else None,
            )
            if status == "error":
                failing += 1
        sources_report.append(
            {
                "name": e.name,
                "enabled": e.enabled,
                "schedule": e.schedule,
                "last_status": status,
                "last_message": message,
                "last_finished_at": finished_at,
            }
        )

    gate = _stop_gate_health()
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "sources": sources_report,
        "sources_failing": failing,
        "tests_ok": gate.get("tests_ok"),
        "tests_checked_at": gate.get("checked_at"),
    }

    if as_json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Sources: {len(sources_report)} configured, {failing} failing on their last run")
        for s in sources_report:
            marker = "!" if s["last_status"] == "error" else " "
            print(f"  {marker} {s['name']:24} {s['last_status']:10} {s['last_message'] or ''}")
        gate_desc = {True: "passing", False: "FAILING", None: "unknown (never run)"}[report["tests_ok"]]
        print(f"Tests/types (last stop-gate check): {gate_desc} (as of {report['tests_checked_at'] or 'n/a'})")

    return 1 if failing else 0


def cmd_probe_sources() -> int:
    """Ping every configured source's declared endpoint (or local file), without writing any
    data — a lighter-weight, more direct check than `refresh` for `source-uptime.yml`'s weekly
    cron. A source with no probe configured is reported, not counted as a failure."""
    import httpx

    from app.config import get_settings
    from app.sources.base import SourceContext

    settings = get_settings()
    failures = 0
    not_probed = 0
    with SessionLocal() as session, httpx.Client() as http:
        ctx = SourceContext(session=session, settings=settings, http=http)
        for e in load_sources():
            try:
                ok, detail = e.source.probe(ctx)
            except Exception as exc:  # noqa: BLE001 - a probe bug shouldn't crash the whole run
                ok, detail = False, f"probe() raised {type(exc).__name__}: {exc}"
            if ok is None:
                not_probed += 1
                print(f"  ? {e.name:24} {detail}")
            elif ok:
                print(f"  . {e.name:24} {detail}")
            else:
                failures += 1
                print(f"  ! {e.name:24} {detail}")
    print(f"\n{failures} failing, {not_probed} not probed, {len(load_sources()) - failures - not_probed} ok")
    return 1 if failures else 0


def cmd_status(as_json: bool) -> int:
    """Report what each phase has actually delivered, by checking docs/phases.yaml against the
    filesystem. This asserts nothing and reads no stored summary: every line is recomputed from
    disk at call time, so a phase can never be reported done because someone wrote that down once
    and the code moved on underneath it."""
    import yaml

    manifest = PROJECT_ROOT / "docs" / "phases.yaml"
    if not manifest.exists():
        print(f"missing {manifest.relative_to(PROJECT_ROOT)} — cannot report status", file=sys.stderr)
        return 1
    phases = yaml.safe_load(manifest.read_text())["phases"]

    report = []
    for phase in phases:
        missing = []
        for check in phase.get("checks") or []:
            target = PROJECT_ROOT / check["path"]
            needle = check.get("contains")
            if not target.exists():
                missing.append(check["path"])
            elif needle and (not target.is_file() or needle not in target.read_text(errors="replace")):
                missing.append(f"{check['path']} (no '{needle}')")
        total = len(phase.get("checks") or [])
        report.append(
            {
                "id": str(phase["id"]),
                "name": phase["name"],
                "present": total - len(missing),
                "total": total,
                "missing": missing,
                "manual": phase.get("manual") or [],
            }
        )

    if as_json:
        print(json.dumps({"checked_at": datetime.now(UTC).isoformat(), "phases": report}, indent=2))
        return 0

    for p in report:
        mark = "done" if not p["missing"] else f"{p['present']}/{p['total']}"
        print(f"\nPhase {p['id']} — {p['name']}: {mark}")
        for m in p["missing"]:
            print(f"    missing  {m}")
        for note in p["manual"]:
            print(f"    manual?  {note}")
    print("\n(manual items are user-side setup — this command cannot verify them)")
    return 0


def cmd_research_gaps() -> int:
    """Write research/gaps.json: valuation factors with no real data source wired, for the
    research-analyst subagent to search against (it reads this file first, every time)."""
    from app.services import MarketContext
    from app.valuation.factors import FACTOR_DEFS, PropertyProfile, market_estimate

    research_dir = PROJECT_ROOT / "research"
    research_dir.mkdir(exist_ok=True)
    with SessionLocal() as session:
        ctx = MarketContext.load(session)
        sample_nta = next(iter(ctx.scores), None)
        estimates = market_estimate(ctx, PropertyProfile(price=1_000_000, nta_code=sample_nta))
    gaps = [
        {"factor": f.key, "label": f.label, "reason": "no live data source wired; falls back to a fixed default"}
        for f in FACTOR_DEFS
        if estimates.get(f.key) is None
    ]
    payload = {"generated_at": datetime.now(UTC).isoformat(), "gaps": gaps}
    (research_dir / "gaps.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(f"{len(gaps)} gap(s) written to research/gaps.json")
    for g in gaps:
        print(f"  - {g['factor']}: {g['label']}")
    return 0


def cmd_research_precision(as_json: bool) -> int:
    """Approved / decided — whether the research agent is earning its budget."""
    from app.research import registry

    entries = registry.load()
    stats = registry.precision(entries)
    if as_json:
        print(json.dumps(stats, indent=2))
        return 0
    print(f"{stats['proposed']} proposed, {stats['decided']} decided, {stats['approved']} approved")
    if stats["precision"] is None:
        print("precision: n/a — nothing decided yet")
    else:
        print(f"precision: {stats['precision']:.0%}")
    for entry in sorted(entries, key=lambda e: e.slug):
        print(f"  {entry.status:12} {entry.slug:28} {entry.decided_at}  {entry.notes}")
    return 0


def cmd_criteria(as_json: bool) -> int:
    """Validate research/criteria.yaml and count entries by status. Non-zero exit on problems so an
    agent that just edited the ledger finds out immediately."""
    from app.research import criteria
    from app.valuation.factors import FACTOR_DEFS

    entries = criteria.load()
    problems = criteria.validate(entries, {f.key for f in FACTOR_DEFS})
    counts = criteria.summary(entries)
    if as_json:
        print(json.dumps({"counts": counts, "problems": problems}, indent=2))
        return 1 if problems else 0
    print(", ".join(f"{n} {s}" for s, n in counts.items()))
    for p in problems:
        print(f"  problem  {p}")
    print("ledger ok" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


def cmd_find_listing_urls(limit: int, listing_id: int | None) -> int:
    """Find public listing-page URLs (links only) via Perplexity's Search API. See app/pipeline/listing_urls.py."""
    import httpx

    from app.config import get_settings
    from app.models import Listing, ListingStatus
    from app.pipeline import listing_urls

    key = get_settings().perplexity_api_key
    if not key:
        print("skipped: PERPLEXITY_API_KEY is not set (read docs/DATA_LICENSES.md before enabling)")
        return 0
    with SessionLocal() as session, httpx.Client() as http:
        q = session.query(Listing).filter(Listing.status == ListingStatus.ACTIVE)
        if listing_id is not None:
            q = q.filter(Listing.id == listing_id)
        listings = [
            type("L", (), {"id": r.id, "address": r.address, "unit": r.unit, "borough": None})
            for r in q.order_by(Listing.id).limit(2000)
        ]
        try:
            stats = listing_urls.find_urls(session, http, key, listings, limit=limit)
        except RuntimeError as e:
            print(f"error: {e}")
            return 1
        print(stats, f"| requests this month: {listing_urls.requests_used(session)}/{listing_urls.MONTHLY_LIMIT}")
    return 0


def cmd_add_region(name: str, watch: bool) -> int:
    """Load a metro's census tracts into `areas` so it can be scored like NYC."""
    import httpx

    from app.config import get_settings
    from app.pipeline.areas import ensure_region, resolve_region, sync_nyc_ntas
    from app.sources.base import SourceContext
    from app.sources.tigerweb import TigerwebTracts

    known = resolve_region(name)
    if known is None:
        from app.pipeline.areas import KNOWN_REGIONS

        print(f"Unknown region {name!r}. Known: {', '.join(sorted(KNOWN_REGIONS))}")
        return 1

    with SessionLocal() as session:
        region = ensure_region(session, known.kind, known.code, known.name, known.state_fips)
        if watch and not region.watched:
            region.watched = True
            session.commit()
        with httpx.Client(follow_redirects=True) as http:
            ctx = SourceContext(session=session, settings=get_settings(), http=http, region=region)
            source = TigerwebTracts("tigerweb_tracts", known_region=known)
            tracts = source.run(ctx)
        ntas = sync_nyc_ntas(session) if known.code == "35620" else 0
    print(f"{known.name}: {tracts} tracts loaded across {len(known.counties)} counties")
    if ntas:
        print(f"  plus {ntas} NYC neighborhoods mirrored into areas")
    print(f"  watched={'yes' if watch else 'no'}")
    return 0


def cmd_valuation_eval(write_baseline: bool, as_json: bool) -> int:
    """Walk-forward accuracy of the comparable-sales value estimate, gated on the stored baseline."""
    from app.valuation import eval as valuation_eval

    with SessionLocal() as session:
        result = valuation_eval.run_eval(session)
    baseline = valuation_eval.load_baseline()
    ok, message = valuation_eval.check_against_baseline(result, baseline)

    if write_baseline:
        valuation_eval.write_baseline(result)
        message = f"Baseline written to research/evals/baseline.json. {message}"
        ok = True
    if as_json:
        print(json.dumps({**result.to_json(), "ok": ok, "message": message}, indent=2))
    else:
        error = result.median_abs_pct_error
        print(f"median absolute % error: {f'{error:.2%}' if error is not None else 'n/a'}")
        print(f"scored {result.n_scored} of {result.n_candidates} sales (coverage {result.coverage:.1%})")
        print(message)
    return 0 if ok else 1


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    refresh = sub.add_parser("refresh", help="run data sources (all enabled if none given), then rescore")
    refresh.add_argument("names", nargs="*")
    sub.add_parser("sources", help="list configured sources")
    sub.add_parser("rescore", help="recompute neighborhood scores only")
    sub.add_parser("backtest", help="run the growth-score backtest")
    diagnose = sub.add_parser("diagnose", help="health snapshot: source status + cached test/type result")
    diagnose.add_argument("--json", action="store_true", dest="as_json")
    sub.add_parser("probe-sources", help="ping every source's declared endpoint, write nothing")
    status = sub.add_parser("status", help="what each phase has actually delivered (checked against disk)")
    status.add_argument("--json", action="store_true", dest="as_json")
    sub.add_parser("research-gaps", help="write research/gaps.json: valuation factors with no real data source")
    research_precision = sub.add_parser("research-precision", help="approved/decided ratio for proposed data sources")
    research_precision.add_argument("--json", action="store_true", dest="as_json")
    criteria_cmd = sub.add_parser("criteria", help="validate research/criteria.yaml and count entries by status")
    criteria_cmd.add_argument("--json", action="store_true", dest="as_json")
    flu = sub.add_parser("find-listing-urls", help="find public listing-page links via Perplexity Search (paid, capped)")
    flu.add_argument("--limit", type=int, default=25, help="max requests this run (each costs about $0.005)")
    flu.add_argument("--id", type=int, dest="listing_id", help="only this listing id")
    sub.add_parser("rescore-areas", help="recompute area Growth Scores within each comparison set")
    add_region = sub.add_parser("add-region", help="load a metro's census tracts into areas")
    add_region.add_argument("name", help="metro nickname, e.g. austin")
    add_region.add_argument("--watch", action="store_true", help="refresh this region on schedule")
    valuation_eval = sub.add_parser("valuation-eval", help="walk-forward accuracy of the comps value estimate")
    valuation_eval.add_argument("--write-baseline", action="store_true", dest="write_baseline")
    valuation_eval.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    if args.cmd == "status":
        return cmd_status(args.as_json)  # reads only the manifest and the filesystem; no DB needed

    if args.cmd == "probe-sources":
        # Needs the DB (for SourceContext) but not a full init_db(); harmless either way.
        init_db()
        return cmd_probe_sources()

    init_db()
    if args.cmd == "sources":
        for e in load_sources():
            print(f"{e.name:24} {e.source.kind:12} enabled={e.enabled!s:5} schedule={e.schedule}")
    elif args.cmd == "refresh":
        for run in run_pipeline(args.names or None):
            print(f"{run.source:24} {run.status:8} records={run.records:<8} {run.message or ''}")
    elif args.cmd == "rescore":
        from app.scoring.neighborhood import recompute_scores

        with SessionLocal() as s:
            print(f"scored {recompute_scores(s)} neighborhoods")
    elif args.cmd == "backtest":
        from app.scoring.backtest import run_backtest

        with SessionLocal() as s:
            print(json.dumps(run_backtest(s), indent=2))
    elif args.cmd == "diagnose":
        return cmd_diagnose(args.as_json)
    elif args.cmd == "research-gaps":
        return cmd_research_gaps()
    elif args.cmd == "research-precision":
        return cmd_research_precision(args.as_json)
    elif args.cmd == "criteria":
        return cmd_criteria(args.as_json)
    elif args.cmd == "find-listing-urls":
        return cmd_find_listing_urls(args.limit, args.listing_id)
    elif args.cmd == "rescore-areas":
        from app.scoring.area import recompute_area_scores

        with SessionLocal() as s:
            print(f"scored {recompute_area_scores(s)} areas")
    elif args.cmd == "add-region":
        return cmd_add_region(args.name, args.watch)
    elif args.cmd == "valuation-eval":
        return cmd_valuation_eval(args.write_baseline, args.as_json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
