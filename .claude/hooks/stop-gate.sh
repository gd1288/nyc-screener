#!/bin/bash
# Stop hook: if backend/ or frontend/ changed (uncommitted), run the fast checks for whichever
# side changed and block ending the turn until they pass. Writes .claude/state/health.json for the
# status line and the (silent-when-healthy) SessionStart hook to read — no extra model calls.
set -uo pipefail

# Hooks run in a stripped-down, non-login shell that doesn't source ~/.zshrc or
# ~/.bash_profile, so a locally-installed Node (this machine keeps it under
# ~/.local/node/bin, added to PATH only by those rc files) is otherwise invisible here.
export PATH="$HOME/.local/node/bin:$PATH"

ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$ROOT" || exit 0
STATE_DIR="$ROOT/.claude/state"
mkdir -p "$STATE_DIR"
HEALTH_FILE="$STATE_DIR/health.json"

CHANGED=$(git status --porcelain 2>/dev/null | cut -c4-)
BACKEND_CHANGED=0
FRONTEND_CHANGED=0
echo "$CHANGED" | grep -q '^backend/' && BACKEND_CHANGED=1
echo "$CHANGED" | grep -q '^frontend/' && FRONTEND_CHANGED=1

FAIL=0
DETAIL=""

if [[ "$BACKEND_CHANGED" == "1" ]]; then
  OUT=$(cd backend && uv run pytest -q 2>&1)
  if [[ $? -ne 0 ]]; then
    FAIL=1
    DETAIL="pytest failing:
$(echo "$OUT" | tail -30)"
  fi
fi

if [[ "$FRONTEND_CHANGED" == "1" && "$FAIL" == "0" ]]; then
  OUT=$(cd frontend && npx tsc --noEmit 2>&1)
  if [[ $? -ne 0 ]]; then
    FAIL=1
    DETAIL="tsc failing:
$(echo "$OUT" | tail -30)"
  fi
fi

NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
if [[ "$FAIL" == "1" ]]; then
  python3 - "$HEALTH_FILE" "$NOW" <<'PYEOF'
import json, sys
path, now = sys.argv[1], sys.argv[2]
json.dump({"tests_ok": False, "checked_at": now}, open(path, "w"))
PYEOF
  echo "Tests/types are failing after this change:" >&2
  echo "$DETAIL" >&2
  exit 2
fi

python3 - "$HEALTH_FILE" "$NOW" <<'PYEOF'
import json, sys
path, now = sys.argv[1], sys.argv[2]
json.dump({"tests_ok": True, "checked_at": now}, open(path, "w"))
PYEOF
exit 0
