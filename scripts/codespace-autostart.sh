#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="/tmp/lucyworks-codespace.log"
API_LOG="/tmp/lucyworks-api.log"
WEB_LOG="/tmp/lucyworks-web.log"

cd "$ROOT"

{
  echo "== LucyWorks OS Codespace autostart =="
  echo "Root: $ROOT"
  echo "Started: $(date -Iseconds)"
  echo "Mode: force-clean restart of ports 8000 and 3000"
} > "$LOG_FILE"

# Kill stale processes that can leave Codespaces port previews blank/502.
for port in 3000 8000; do
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${port}/tcp" >> "$LOG_FILE" 2>&1 || true
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti tcp:"$port" | xargs -r kill -9 >> "$LOG_FILE" 2>&1 || true
  fi
done

(
  set -euo pipefail
  echo "Installing API dependencies..." >> "$LOG_FILE"
  cd "$ROOT/apps/api"
  python -m pip install -r requirements.txt >> "$API_LOG" 2>&1
  echo "Starting API on 8000..." >> "$LOG_FILE"
  exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 >> "$API_LOG" 2>&1
) &
API_PID=$!

(
  set -euo pipefail
  echo "Installing web dependencies..." >> "$LOG_FILE"
  cd "$ROOT/apps/web"
  npm install >> "$WEB_LOG" 2>&1
  echo "Starting web on 3000..." >> "$LOG_FILE"
  exec env NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev -- --hostname 0.0.0.0 --port 3000 >> "$WEB_LOG" 2>&1
) &
WEB_PID=$!

{
  echo "API PID: $API_PID"
  echo "WEB PID: $WEB_PID"
  echo "Web: http://localhost:3000"
  echo "API: http://localhost:8000"
  echo "API log: $API_LOG"
  echo "Web log: $WEB_LOG"
} >> "$LOG_FILE"

# Print a quick live status without failing the Codespace attach hook.
sleep 5
if command -v curl >/dev/null 2>&1; then
  curl -fsS http://localhost:8000/api/health >> "$LOG_FILE" 2>&1 || echo "API health not ready yet" >> "$LOG_FILE"
  curl -fsS http://localhost:3000 >> "$LOG_FILE" 2>&1 || echo "Web not ready yet" >> "$LOG_FILE"
fi

echo "Autostart dispatched. Open Codespaces PORTS → 3000 when ready." >> "$LOG_FILE"
