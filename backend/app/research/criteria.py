"""The criteria ledger (research/criteria.yaml): load, validate, summarise.

The ledger is the link between research and the product: criterion -> approval -> valuation factor
-> UI element. Agents append rows to it, so it is validated in code rather than trusted: a malformed
row, an `approved` entry nobody dated, or a `live` entry pointing at a factor that does not exist
would otherwise quietly rot the one file every new session is told to rely on.

UI suggestions are allowed but only ever aimed at the staging artifact; main is changed by promotion,
with the user's explicit approval (see CLAUDE.md).
"""

from collections import Counter
from pathlib import Path

import yaml

LEDGER_PATH = Path(__file__).resolve().parents[3] / "research" / "criteria.yaml"
STATUSES = ("gap", "idea", "proposed", "approved", "live", "rejected")
UI_TARGET = "staging"


def load(path: Path = LEDGER_PATH) -> list[dict]:
    if not path.exists():
        return []
    return (yaml.safe_load(path.read_text()) or {}).get("criteria") or []


def validate(entries: list[dict], factor_keys: set[str]) -> list[str]:
    """Return human-readable problems; an empty list means the ledger is sound."""
    problems: list[str] = []
    seen: set[str] = set()
    for i, e in enumerate(entries):
        cid = e.get("id")
        where = f"entry {i} ({cid or '?'})"
        for field in ("id", "label", "status"):
            if not e.get(field):
                problems.append(f"{where}: missing '{field}'")
        if cid in seen:
            problems.append(f"{where}: duplicate id")
        seen.add(cid)
        status = e.get("status")
        if status and status not in STATUSES:
            problems.append(f"{where}: unknown status '{status}' (use one of {', '.join(STATUSES)})")
        if status in ("approved", "live", "rejected") and not e.get("decided"):
            problems.append(f"{where}: status '{status}' needs a 'decided' date")
        if status == "rejected" and not e.get("reason"):
            problems.append(f"{where}: rejected needs a 'reason'")
        if status == "live" and e.get("factor") not in factor_keys:
            problems.append(f"{where}: live but factor '{e.get('factor')}' is not in valuation/factors.py")
        suggestion = e.get("ui_suggestion")
        if suggestion is not None and (
            not isinstance(suggestion, dict)
            or suggestion.get("target") != UI_TARGET
            or not suggestion.get("description")
        ):
            problems.append(f"{where}: ui_suggestion needs target '{UI_TARGET}' and a description")
    return problems


def summary(entries: list[dict]) -> dict[str, int]:
    counts = Counter(e.get("status", "?") for e in entries)
    return {s: counts.get(s, 0) for s in STATUSES}
