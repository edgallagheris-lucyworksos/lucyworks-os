#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "== LucyWorks OS: dev runner =="
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo ""

echo "Starting backend and frontend. Press Ctrl+C to stop both."

cleanup() {
  echo "\nStopping LucyWorks OS..."
  jobs -p | xargs -r kill
}
trap cleanup EXIT

(
  cd "$ROOT_DIR/backend"
  python -m pip install --upgrade pip >/dev/null
  pip install -r requirements.txt >/dev/null
  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
) &

(
  cd "$ROOT_DIR/frontend"
  npm install >/dev/null
  NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev -- --hostname 0.0.0.0 --port 3000
) &

wait
