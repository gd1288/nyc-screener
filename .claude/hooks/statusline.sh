#!/bin/bash
# Status line: model, context window %, session cost, and a health badge from the cached
# .claude/state/health.json (written by stop-gate.sh). Runs locally on every render — reads
# cached JSON only, no model tokens, no live checks.
set -uo pipefail

INPUT=$(cat)
MODEL=$(echo "$INPUT" | jq -r '.model.display_name // "?"')
COST=$(echo "$INPUT" | jq -r '.cost.total_cost_usd // 0')
USED=$(echo "$INPUT" | jq -r '.context_window.total_input_tokens // 0')
MAX=$(echo "$INPUT" | jq -r '.context_window.context_window_size // 200000')
DIR=$(basename "$(echo "$INPUT" | jq -r '.workspace.current_dir // "."')")

PCT=0
if [[ "$MAX" != "0" ]]; then
  PCT=$(( USED * 100 / MAX ))
fi

ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
HEALTH_FILE="$ROOT/.claude/state/health.json"
BADGE="●"
if [[ -f "$HEALTH_FILE" ]]; then
  OK=$(python3 -c "import json; print(json.load(open('$HEALTH_FILE')).get('tests_ok', True))" 2>/dev/null)
  [[ "$OK" == "False" ]] && BADGE="✗ failing" || BADGE="✓ ok"
else
  BADGE="? unknown"
fi

printf "%s 📁 %s | %d%% ctx | \$%.3f | %s\n" "$MODEL" "$DIR" "$PCT" "$COST" "$BADGE"
