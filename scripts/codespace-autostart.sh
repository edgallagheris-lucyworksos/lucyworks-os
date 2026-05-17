#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="/tmp/lucyworks-codespace.log"
PID_FILE="/tmp/lucyworks-codespace.pid"

cd "$ROOT"

echo "== LucyWorks OS Codespace autostart ==" > "$LOG_FILE"
echo "Root: $ROOT" >> "$LOG_FILE"
echo "Started: $(date -Iseconds)" >> "$LOG_FILE"

if [ -f "$PID_FILE" ]; then
  OLD_PID="$(cat "$PID_FILE" || true)"
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "LucyWorks OS already running under PID $OLD_PID" >> "$LOG_FILE"
    exit 0
  fi
fi

(
  echo "Installing API dependencies..." >> "$LOG_FILE"
  cd "$ROOT/apps/api"
  python -m pip install -r requirements.txt >> "$LOG_FILE" 2>&1
  echo "Starting API on 8000..." >> "$LOG_FILE"
  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 >> "$LOG_FILE" 2>&1
) &
API_PID=$!

(
  echo "Installing web dependencies..." >> "$LOG_FILE"
  cd "$ROOT/apps/web"
  npm install >> "$LOG_FILE" 2>&1
  echo "Starting web on 3000..." >> "$LOG_FILE"
  NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev -- --hostname 0.0.0.0 --port 3000 >> "$LOG_FILE" 2>&1
) &
WEB_PID=$!

echo "$WEB_PID" > "$PID_FILE"
echo "API PID: $API_PID" >> "$LOG_FILE"
echo "WEB PID: $WEB_PID" >> "$LOG_FILE"
echo "Web: http://localhost:3000" >> "$LOG_FILE"
echo "API: http://localhost:8000" >> "$LOG_FILE"
