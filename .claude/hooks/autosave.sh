#!/bin/bash
# Autosave: keeps this project recoverable from a new window or machine without anyone remembering to.
# Runs after every response (Stop hook) and at session end. It NEVER fails the session and NEVER touches your
# branch, index or files. What it does:
#   1. Snapshots all uncommitted and untracked work (respecting .gitignore, so keys and the database are never
#      included) as a commit on a separate ref, refs/autosave/<branch>, using a temporary index.
#   2. Adds a copy of Claude's memory notes for this project under .claude/memory-backup/ inside that snapshot.
#   3. Refuses to snapshot if the changes look like they contain a secret (logged, nothing pushed).
#   4. Only when .claude/autosave.json says {"push": true}: pushes the autosave ref, the current branch (never
#      main/master) and any new tags to origin, in the background. Pushing is OFF by default: the GitHub repo may
#      be public, and staging.html embeds third-party data. Turn it on only after deciding that.
# Log: .claude/state/autosave.log (git-ignored). Restore steps: docs/SESSIONS.md.
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$ROOT" 2>/dev/null || exit 0
git rev-parse --git-dir >/dev/null 2>&1 || exit 0
BR=$(git branch --show-current)
[[ -n "$BR" ]] || exit 0
LOGF="$ROOT/.claude/state/autosave.log"
mkdir -p "$(dirname "$LOGF")"
log() { echo "$(date '+%F %T') [$BR] $*" >> "$LOGF"; }

PUSH=$(python3 -c "import json,sys;print(json.load(open('$ROOT/.claude/autosave.json')).get('push', False))" 2>/dev/null || echo False)

# ---- 1 + 2: snapshot into a temporary index (the real index and working tree are never touched)
TMPIDX=$(mktemp -t autosave-index.XXXXXX)
trap 'rm -f "$TMPIDX"' EXIT
export GIT_INDEX_FILE="$TMPIDX"
git read-tree HEAD 2>/dev/null || { log "read-tree failed"; exit 0; }
git add -A -- . 2>/dev/null

MEM="$HOME/.claude/projects/$(echo "$ROOT" | sed 's|/|-|g')/memory"
if [[ -d "$MEM" ]]; then
  for f in "$MEM"/*.md; do
    [[ -f "$f" ]] || continue
    h=$(git hash-object -w "$f") && git update-index --add --cacheinfo "100644,$h,.claude/memory-backup/$(basename "$f")"
  done
fi

# ---- 3: secret guard on what would be snapshotted (added lines only)
if git diff --cached -U0 HEAD 2>/dev/null | grep -Ei "^\+.*(api[_-]?key|token|secret|password)[\"' ]*[=:][\"' ]*[A-Za-z0-9_-]{24,}" >/dev/null; then
  log "BLOCKED: changes look like they contain a secret; no snapshot, nothing pushed"
  exit 0
fi
if git diff --cached --name-only HEAD 2>/dev/null | grep -Ei "(^|/)\.env($|\.)|\.pem$|id_rsa|\.sqlite$|screener\.db" | grep -v "\.env\.example" >/dev/null; then
  log "BLOCKED: a sensitive file name is in the snapshot; no snapshot, nothing pushed"
  exit 0
fi

TREE=$(git write-tree)
REF="refs/autosave/$BR"
LAST=$(git rev-parse -q --verify "$REF^{tree}" 2>/dev/null || true)
HEADTREE=$(git rev-parse "HEAD^{tree}")
if [[ "$TREE" != "$LAST" && "$TREE" != "$HEADTREE" ]]; then
  COMMIT=$(git commit-tree "$TREE" -p HEAD -m "autosave of $BR at $(date '+%F %T')" 2>/dev/null) && git update-ref "$REF" "$COMMIT" && log "snapshot ${COMMIT:0:9} saved to $REF"
elif [[ "$TREE" == "$HEADTREE" && -n "$LAST" && "$LAST" != "$HEADTREE" ]]; then
  git update-ref -d "$REF" 2>/dev/null && log "everything committed; autosave ref cleared"
else
  log "up to date"
fi
[[ $(wc -l < "$LOGF") -gt 400 ]] && tail -300 "$LOGF" > "$LOGF.tmp" && mv "$LOGF.tmp" "$LOGF"
unset GIT_INDEX_FILE

# ---- 4: optional push, in the background so the session never waits on the network
if [[ "$PUSH" == "True" ]]; then
  (
    cd "$ROOT" || exit 0
    if git rev-parse -q --verify "$REF" >/dev/null 2>&1; then
      timeout 40 git push -q --force origin "$REF:refs/heads/autosave/$BR" >>"$LOGF" 2>&1 && echo "$(date '+%F %T') [$BR] pushed autosave/$BR" >>"$LOGF"
    fi
    if [[ "$BR" != "main" && "$BR" != "master" ]]; then
      timeout 40 git push -q origin "$BR" >>"$LOGF" 2>&1 && echo "$(date '+%F %T') [$BR] pushed branch" >>"$LOGF"
    fi
    timeout 40 git push -q origin --tags >>"$LOGF" 2>&1
  ) >/dev/null 2>&1 &
fi
exit 0
