#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

cd apps/api
python import_all_smoke_test.py
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
[ -f forecast_smoke_test.py ] && python forecast_smoke_test.py || echo "WARN: forecast_smoke_test.py not present"
python - <<'PY'
from app.main import app
print('API startup import OK', bool(app))
PY
cd "$ROOT/packages/shared"
npm install
npm run check
cd "$ROOT/apps/web"
npm install
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run build

echo "MONOREPO CHECK PASSED"
