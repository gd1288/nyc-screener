#!/bin/bash
# PreToolUse guard for the Artifact tool. The approved "main" Real Estate Tool artifact may only be
# changed with the user's explicit approval: this hook turns any change to it into a permission
# prompt (in a non-interactive session an unanswerable prompt means the call does not happen).
# Only the "staging" artifact (see .claude/artifacts.json) may be published freely.
set -euo pipefail

INPUT=$(cat)
[[ "$(echo "$INPUT" | jq -r '.tool_name // empty')" == "Artifact" ]] || exit 0

REG="${CLAUDE_PROJECT_DIR:-.}/.claude/artifacts.json"
ACTION=$(echo "$INPUT" | jq -r '.tool_input.action // "publish"')
URL=$(echo "$INPUT" | jq -r '.tool_input.url // empty')
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
MAIN_ID=$(jq -r '.main.id' "$REG")
STAGING_ID=$(jq -r '.staging.id' "$REG")

case "$ACTION" in
  read|list|comments|status|list_assets|list_files|read_file|read_asset|read_db|watch|unwatch|open|quickstart|list_types|describe_type) exit 0 ;;
esac

ask() {
  jq -n --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$r}}'
  exit 0
}

[[ "$URL" == *"$MAIN_ID"* ]] && ask "This changes the approved MAIN Real Estate Tool artifact. Approve only if you asked for it (promotion from staging)."
[[ "$URL" == *"$STAGING_ID"* ]] && exit 0
# No URL: a publish creates a new artifact, or redeploys whichever URL this file path was last
# published to in this session. Only the staging working copy is known to be safe.
[[ "$FILE" == */docs/artifact/staging.html ]] && exit 0
ask "Artifact change is not clearly aimed at staging (url/file_path do not match .claude/artifacts.json). It could overwrite the main artifact; approve only if intended."
