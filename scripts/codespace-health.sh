#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="/tmp/lucyworks-codespace.log"
API_LOG="/tmp/lucyworks-api.log"
WEB_LOG="/tmp/lucyworks-web.log"

cd "$ROOT"

echo "== LucyWorks OS health check =="
echo "Root: $ROOT"
echo "Time: $(date -Iseconds)"
echo ""

echo "== Git =="
git branch --show-current 2>/dev/null || true
git log -1 --oneline 2>/dev/null || true
echo ""

echo "== Expected paths =="
for path in apps/api apps/web scripts/codespace-autostart.sh .devcontainer/devcontainer.json; do
  if [ -e "$path" ]; then
    echo "OK   $path"
  else
    echo "MISS $path"
  fi
done
echo ""

echo "== Ports =="
if command -v ss >/dev/null 2>&1; then
  ss -ltnp | grep -E ':(3000|8000)\b' || echo "No listeners on 3000/8000"
elif command -v lsof >/dev/null 2>&1; then
  lsof -iTCP -sTCP:LISTEN -P | grep -E ':(3000|8000)\b' || echo "No listeners on 3000/8000"
else
  echo "No ss/lsof available"
fi
echo ""

echo "== API health =="
if command -v curl >/dev/null 2>&1; then
  curl -i --max-time 5 http://localhost:8000/api/health || true
else
  echo "curl missing"
fi
echo ""

echo "== Web health =="
if command -v curl >/dev/null 2>&1; then
  curl -I --max-time 5 http://localhost:3000 || true
else
  echo "curl missing"
fi
echo ""

echo "== Main autostart log =="
if [ -f "$LOG_FILE" ]; then
  tail -80 "$LOG_FILE"
else
  echo "Missing $LOG_FILE"
fi
echo ""

echo "== API log tail =="
if [ -f "$API_LOG" ]; then
  tail -80 "$API_LOG"
else
  echo "Missing $API_LOG"
fi
echo ""

echo "== Web log tail =="
if [ -f "$WEB_LOG" ]; then
  tail -120 "$WEB_LOG"
else
  echo "Missing $WEB_LOG"
fi
