#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== LucyWorks operational proof v30 =="
python scripts/validate_operational_proof_v30.py

cd "$ROOT/apps/api"
python -m pip install --upgrade pip -q
python -m pip install -q -r requirements.txt
python -m py_compile \
  app/operational_proof_v30_models.py \
  app/operational_proof_v30_routes.py \
  app/connected_surfaces_v30_patch.py \
  app/production_readiness_v30_patch.py \
  operational_proof_v30_smoke_test.py \
  operational_proof_v30_authority_test.py \
  migrations/versions/0024_operational_proof_v30.py
python hospital_command_v9_smoke_test.py
python operational_proof_v30_smoke_test.py
python operational_proof_v30_authority_test.py

cd "$ROOT/apps/web"
npm install --no-audit --no-fund
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run build

echo "OPERATIONAL_PROOF_V30_ALL_AUTOMATED_CHECKS_PASSED"
echo "Physical Android acceptance and real-hospital UAT remain explicit manual boundaries."
