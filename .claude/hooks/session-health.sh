#!/bin/bash
# SessionStart hook: prints NOTHING when things look healthy (no extra tokens spent on a routine
# session start). Only prints a single line when the last Stop-gate check failed, or a data source's
# most recent run errored — pointing at /debug. Never runs checks itself; only reads cached state.
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
HEALTH_FILE="$ROOT/.claude/state/health.json"
DB="$ROOT/backend/data/screener.db"

MSGS=()

if [[ -f "$HEALTH_FILE" ]]; then
  OK=$(python3 -c "import json; print(json.load(open('$HEALTH_FILE')).get('tests_ok', True))" 2>/dev/null)
  if [[ "$OK" == "False" ]]; then
    MSGS+=("tests/types were failing as of the last change")
  fi
fi

if [[ -f "$DB" ]] && command -v sqlite3 >/dev/null 2>&1; then
  FAILING=$(sqlite3 "$DB" "
    select count(*) from (
      select source, status from source_runs r
      where r.id = (select max(id) from source_runs r2 where r2.source = r.source)
      and r.status = 'error'
    );
  " 2>/dev/null)
  if [[ -n "$FAILING" && "$FAILING" != "0" ]]; then
    MSGS+=("$FAILING data source(s) failing on their last run")
  fi
fi

if [[ ${#MSGS[@]} -gt 0 ]]; then
  JOINED=$(IFS='; '; echo "${MSGS[*]}")
  echo "Health: $JOINED — run 'uv run python -m app.cli diagnose' or /debug"
fi

exit 0
