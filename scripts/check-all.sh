#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "== LucyWorks OS: full system check =="

echo "\n== Backend dependencies =="
cd "$ROOT_DIR/backend"
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "\n== Backend import smoke check =="
python import_all_smoke_test.py

echo "\n== Backend smoke tests =="
python smoke_test.py
python hospital_scale_smoke_test.py
python flow_state_smoke_test.py
python live_action_gate_smoke_test.py
python workspace_smoke_test.py
python catalogue_smoke_test.py
python hr_smoke_test.py
python readiness_smoke_test.py
python input_smoke_test.py
python ops_engine_smoke_test.py
python canonical_v3_smoke_test.py
python canonical_modules_smoke_test.py

if [ -f forecast_smoke_test.py ]; then
  python forecast_smoke_test.py
else
  echo "WARN: forecast_smoke_test.py not present yet"
fi

echo "\n== Frontend dependencies/build =="
cd "$ROOT_DIR/frontend"
npm install
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run build

echo "\n== DONE: backend smoke tests + frontend build completed =="
