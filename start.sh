#!/usr/bin/env bash
# Starts the API (with scheduled data refreshes) and the web app. Open http://localhost:3000
set -e
cd "$(dirname "$0")"
export PATH="$HOME/.local/node/bin:$HOME/.local/bin:$PATH"

(cd backend && uv run uvicorn app.main:app --port 8000) &
API_PID=$!
trap 'kill $API_PID 2>/dev/null' EXIT

cd frontend
[ -d node_modules ] || npm install
npm run dev -- --port 3000
