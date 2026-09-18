"""What the research agent has already proposed, and what you decided about it.

Without this the agent re-proposes the same rejected source every run, and its budget goes on
rediscovering answers you already gave. The registry is the first thing the `research-sources` skill
reads, before it spends a single search.

A rejection is a cooldown, not a tombstone: a source rejected because its data was too thin may be
worth another look next year, so `REJECTION_COOLDOWN_DAYS` lets it back in after 90 days. An
approved source is skipped permanently — it is either implemented or tracked as an issue by then.

Kept as JSON in the repo rather than in the database on purpose: these are decisions, they belong in
review alongside the code that acts on them, and the agent that reads them may run in a worktree
with no database.
"""

import json
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

REGISTRY_PATH = Path(__file__).resolve().parents[3] / "research" / "registry.json"
REJECTION_COOLDOWN_DAYS = 90
VERSION = 1

APPROVED = "approved"
REJECTED = "rejected"
PROPOSED = "proposed"
IMPLEMENTED = "implemented"
STATUSES = (PROPOSED, APPROVED, REJECTED, IMPLEMENTED)


@dataclass
class RegistryEntry:
    slug: str
    name: str
    status: str
    decided_at: str  # ISO date
    url: str = ""
    gap: str = ""
    notes: str = ""


def load(path: Path = REGISTRY_PATH) -> list[RegistryEntry]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    return [RegistryEntry(**entry) for entry in payload.get("entries", [])]


def save(entries: list[RegistryEntry], path: Path = REGISTRY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(entries, key=lambda e: (e.slug,))
    path.write_text(json.dumps({"version": VERSION, "entries": [asdict(e) for e in ordered]}, indent=2) + "\n")


def record(entry: RegistryEntry, path: Path = REGISTRY_PATH) -> list[RegistryEntry]:
    """Upsert by slug — a re-decision replaces the old one rather than stacking a second row that
    later reads would have to disambiguate."""
    if entry.status not in STATUSES:
        raise ValueError(f"unknown status {entry.status!r}; expected one of {STATUSES}")
    entries = [e for e in load(path) if e.slug != entry.slug]
    entries.append(entry)
    save(entries, path)
    return entries


def should_skip(slug: str, entries: list[RegistryEntry], today: date | None = None) -> tuple[bool, str]:
    """Whether the agent should skip a candidate it is about to research, and why.

    Returning the reason matters as much as the boolean: a silently skipped candidate looks to the
    user like the agent simply failed to find it.
    """
    today = today or date.today()
    entry = next((e for e in entries if e.slug == slug), None)
    if entry is None:
        return False, ""
    if entry.status in (APPROVED, IMPLEMENTED):
        return True, f"already {entry.status} on {entry.decided_at}"
    if entry.status == REJECTED:
        try:
            decided = date.fromisoformat(entry.decided_at)
        except ValueError:
            return True, f"rejected on an unparseable date ({entry.decided_at!r}) — treating as current"
        reopens = decided + timedelta(days=REJECTION_COOLDOWN_DAYS)
        if today < reopens:
            return True, f"rejected {entry.decided_at}, eligible again {reopens.isoformat()}"
        return False, f"rejected {entry.decided_at} but the {REJECTION_COOLDOWN_DAYS}-day cooldown has passed"
    return False, f"previously proposed on {entry.decided_at}, never decided"


def precision(entries: list[RegistryEntry]) -> dict:
    """Approved ÷ decided — the plan's metric for whether the research agent is worth its budget.

    Undecided proposals are excluded from the denominator rather than counted as failures: a
    candidate nobody has ruled on yet is not evidence either way.
    """
    decided = [e for e in entries if e.status in (APPROVED, REJECTED, IMPLEMENTED)]
    approved = [e for e in decided if e.status in (APPROVED, IMPLEMENTED)]
    return {
        "proposed": len(entries),
        "decided": len(decided),
        "approved": len(approved),
        "precision": round(len(approved) / len(decided), 4) if decided else None,
    }
