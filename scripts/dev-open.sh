#!/usr/bin/env bash
# Start the API and web app if they're not already running, then open the site in your browser.
# Safe to run more than once (e.g. double-clicking the Desktop shortcut again) -- it reuses
# whatever's already up instead of starting a second copy. Servers keep running after this
# script (and its Terminal window) exits.
set -e
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/node/bin:$HOME/.local/bin:$PATH"

mkdir -p /tmp/nyc-screener-logs

if ! lsof -i :8000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Starting the API on :8000 ..."
  (cd backend && nohup uv run uvicorn app.main:app --port 8000 > /tmp/nyc-screener-logs/api.log 2>&1 &)
  disown -a 2>/dev/null || true
else
  echo "API already running on :8000."
fi

if ! lsof -i :3000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Starting the web app on :3000 ..."
  (cd frontend && [ -d node_modules ] || npm install)
  (cd frontend && nohup npm run dev -- --port 3000 > /tmp/nyc-screener-logs/web.log 2>&1 &)
  disown -a 2>/dev/null || true
else
  echo "Web app already running on :3000."
fi

echo "Waiting for the site to come up..."
for _ in $(seq 1 30); do
  if curl -sf http://localhost:3000 > /dev/null 2>&1; then
    break
  fi
  sleep 1
done

open "http://localhost:3000" 2>/dev/null || echo "Open this yourself: http://localhost:3000"

echo
echo "NYC Screener is running:"
echo "  Site:    http://localhost:3000"
echo "  API:     http://localhost:8000"
echo "  Logs:    /tmp/nyc-screener-logs/"
echo
echo "It'll keep running after you close this window. Use 'Stop NYC Screener' on the Desktop"
echo "(or scripts/dev-stop.sh) to shut it down."
echo
read -r -p "Press Enter to close this window..." _ || true
