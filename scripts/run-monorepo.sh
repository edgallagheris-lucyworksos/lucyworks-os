#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
echo "API: http://localhost:8000"
echo "Web: http://localhost:3000"
(
  cd apps/api && python -m pip install -r requirements.txt && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
) &
(
  cd apps/web && npm install && NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev -- --hostname 0.0.0.0 --port 3000
) &
wait
