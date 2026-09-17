#!/bin/bash
# PostToolUse Edit|Write: silently auto-format Python files. Prints nothing on success;
# on failure, prints ruff's own diagnostic so Claude can fix it.
set -uo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

[[ -z "$FILE_PATH" ]] && exit 0
[[ "$FILE_PATH" != *.py ]] && exit 0
[[ "$FILE_PATH" != */backend/* ]] && exit 0
[[ ! -f "$FILE_PATH" ]] && exit 0

BACKEND_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}/backend"
[[ -d "$BACKEND_DIR" ]] || exit 0

cd "$BACKEND_DIR" || exit 0
OUT=$(uv run ruff format "$FILE_PATH" 2>&1 && uv run ruff check --fix "$FILE_PATH" 2>&1)
STATUS=$?
if [[ $STATUS -ne 0 ]]; then
  echo "$OUT" | head -40
  exit 1
fi
exit 0
