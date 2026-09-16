"""Command line: `uv run python -m app.cli refresh [source ...]`, `... sources`, `... backtest`."""

import argparse
import json
import logging

from app.db import SessionLocal, init_db
from app.sources.registry import load_sources, run_pipeline


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    refresh = sub.add_parser("refresh", help="run data sources (all enabled if none given), then rescore")
    refresh.add_argument("names", nargs="*")
    sub.add_parser("sources", help="list configured sources")
    sub.add_parser("rescore", help="recompute neighborhood scores only")
    sub.add_parser("backtest", help="run the growth-score backtest")
    args = parser.parse_args()

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


if __name__ == "__main__":
    main()
