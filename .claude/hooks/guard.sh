#!/bin/bash
# PreToolUse guard for Edit|Write|Bash: blocks edits to secrets/data files and unsafe commands.
# Exit 2 blocks the tool call and feeds stderr back to Claude as the reason.
set -euo pipefail

INPUT=$(cat)
TOOL=$(echo "$INPUT" | jq -r '.tool_name // empty')

block() {
  echo "Blocked: $1" >&2
  exit 2
}

if [[ "$TOOL" == "Edit" || "$TOOL" == "Write" ]]; then
  FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
  FILE_PATH="${FILE_PATH//\\//}"
  case "$FILE_PATH" in
    *.env.example|*.env.*.example) : ;;  # committed templates are fine
    *.env|*.env.*) block "editing .env files is not allowed (it holds live API keys)." ;;
    */backend/data/*) block "editing files under backend/data/ (the live database and its journal) is not allowed." ;;
    *package-lock.json|*uv.lock) block "editing a lockfile directly is not allowed — regenerate it with npm/uv instead." ;;
    */.git/*) block "editing files under .git/ is not allowed." ;;
  esac
fi

if [[ "$TOOL" == "Bash" ]]; then
  CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
  if echo "$CMD" | grep -qE '(^|[^A-Za-z0-9._-])api\.rentcast\.io([^A-Za-z0-9._-]|$)'; then
    block "direct calls to api.rentcast.io are not allowed — the RentCast budget/cooldown lives in app/sources/rentcast.py. Use the adapter (uv run python -m app.cli refresh rentcast_listings) instead."
  fi
  if echo "$CMD" | grep -qE '\brm\s+.*backend/data/'; then
    block "deleting files under backend/data/ is not allowed — that's the live database."
  fi
  # Only fire when a file-reading command is actually invoked AND a bare .env token
  # appears somewhere in the line — matching on ".env" alone would also catch it inside
  # ordinary prose, e.g. a commit message describing this very rule.
  if echo "$CMD" | grep -qE '(^|[[:space:]])(cat|less|more|head|tail|vi|vim|nano|cp|mv|scp|source|xxd|strings|python[0-9.]*|node)([[:space:]]|$)' \
     && echo "$CMD" | grep -qE '(^|[^A-Za-z0-9._-])\.env([^A-Za-z0-9._-]|$)'; then
    block "reading .env via Bash is not allowed (it holds live API keys) — the Read tool already denies it; don't route around that with Bash."
  fi
fi

exit 0
