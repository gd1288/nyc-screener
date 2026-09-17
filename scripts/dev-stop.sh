#!/usr/bin/env bash
# Stop the API and web app started by dev-open.sh (or start.sh).
set -e

stopped_any=0
for port in 8000 3000; do
  pid=$(lsof -ti :"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [ -n "$pid" ]; then
    echo "Stopping process on :$port (pid $pid)"
    kill "$pid" 2>/dev/null || true
    stopped_any=1
  fi
done

if [ "$stopped_any" = "0" ]; then
  echo "Nothing was running on :8000 or :3000."
else
  echo "Stopped."
fi

read -r -p "Press Enter to close this window..." _ || true
