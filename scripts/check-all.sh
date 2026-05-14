#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "== LucyWorks OS: full system check =="

echo "\n== Backend dependencies =="
cd "$ROOT_DIR/backend"
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "\n== Backend import/smoke checks =="
python import_all_smoke_test.py
python canonical_modules_smoke_test.py

echo "\n== Frontend dependencies/build =="
cd "$ROOT_DIR/frontend"
npm install
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run build

echo "\n== DONE: backend import checks + frontend build completed =="
