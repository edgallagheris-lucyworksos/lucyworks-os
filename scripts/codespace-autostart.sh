#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="/tmp/lucyworks-codespace.log"
API_LOG="/tmp/lucyworks-api.log"
WEB_LOG="/tmp/lucyworks-web.log"

cd "$ROOT"

{
  echo "== LucyWorks OS Codespace runner =="
  echo "Root: $ROOT"
  echo "Started: $(date -Iseconds)"
  echo "Mode: resilient foreground runner for ports 8000 and 3000"
} | tee "$LOG_FILE"

# Kill stale processes that can leave Codespaces port previews blank/502.
for port in 3000 8000; do
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${port}/tcp" >> "$LOG_FILE" 2>&1 || true
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti tcp:"$port" | xargs -r kill -9 >> "$LOG_FILE" 2>&1 || true
  fi
done

cleanup() {
  echo "Stopping LucyWorks OS dev servers..." | tee -a "$LOG_FILE"
  jobs -p | xargs -r kill >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

(
  set -euo pipefail
  cd "$ROOT/apps/api"
  echo "Installing API dependencies..." | tee -a "$LOG_FILE"
  python -m pip install -r requirements.txt 2>&1 | tee "$API_LOG"
  echo "Starting API on 8000..." | tee -a "$LOG_FILE"
  python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 2>&1 | tee -a "$API_LOG"
  echo "API process exited. Web may still be running; check $API_LOG" | tee -a "$LOG_FILE"
) &
API_PID=$!

(
  set -euo pipefail
  cd "$ROOT/apps/web"
  echo "Installing web dependencies..." | tee -a "$LOG_FILE"
  npm install 2>&1 | tee "$WEB_LOG"
  echo "Starting web on 3000..." | tee -a "$LOG_FILE"
  env NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev -- --hostname 0.0.0.0 --port 3000 2>&1 | tee -a "$WEB_LOG"
  echo "Web process exited. Check $WEB_LOG" | tee -a "$LOG_FILE"
) &
WEB_PID=$!

{
  echo "API PID: $API_PID"
  echo "WEB PID: $WEB_PID"
  echo "Web: http://localhost:3000"
  echo "Board: http://localhost:3000/hospital-board"
  echo "API: http://localhost:8000"
  echo "API log: $API_LOG"
  echo "Web log: $WEB_LOG"
  echo ""
  echo "Keep this terminal open. Backend failure will not kill the web preview."
  echo "If the browser shows 502, run: npm run codespace:health"
} | tee -a "$LOG_FILE"

set +e
wait "$WEB_PID"
WEB_EXIT=$?
wait "$API_PID"
API_EXIT=$?
set -e

echo "Web exited with code $WEB_EXIT" | tee -a "$LOG_FILE"
echo "API exited with code $API_EXIT" | tee -a "$LOG_FILE"
exit "$WEB_EXIT"