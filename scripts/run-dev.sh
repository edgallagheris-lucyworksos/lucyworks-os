#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "== LucyWorks OS: monorepo dev runner =="
echo "API:  http://localhost:8000"
echo "Web:  http://localhost:3000"
echo "Board: http://localhost:3000/hospital-board"
echo ""

echo "Starting apps/api and apps/web. Press Ctrl+C to stop both."

cleanup() {
  echo "\nStopping LucyWorks OS..."
  jobs -p | xargs -r kill
}
trap cleanup EXIT

(
  cd "$ROOT_DIR/apps/api"
  python -m pip install --upgrade pip >/dev/null
  python -m pip install -r requirements.txt >/dev/null
  python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
) &

(
  cd "$ROOT_DIR/apps/web"
  npm install >/dev/null
  NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev -- --hostname 0.0.0.0 --port 3000
) &

wait
