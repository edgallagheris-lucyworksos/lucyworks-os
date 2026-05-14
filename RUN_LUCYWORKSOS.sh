#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

say() { printf "\n== %s ==\n" "$1"; }
warn() { printf "\nWARN: %s\n" "$1"; }
fail() { printf "\nERROR: %s\n" "$1"; exit 1; }

say "LucyWorksOS: professional hospital operating system runner"
printf "Repo: %s\n" "$ROOT_DIR"

if ! command -v git >/dev/null 2>&1; then
  fail "git is not available in this environment"
fi
if ! command -v npm >/dev/null 2>&1; then
  fail "npm is not available in this environment"
fi
if ! command -v python >/dev/null 2>&1; then
  fail "python is not available in this environment"
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
UPSTREAM="$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)"
printf "Branch: %s\n" "$BRANCH"
printf "Upstream: %s\n" "${UPSTREAM:-none}"

say "Sync latest code when safe"
if [ -n "$UPSTREAM" ]; then
  git pull --ff-only
else
  warn "branch has no upstream; skipping git pull and continuing local run"
fi

say "Runtime check"
PY_VERSION="$(python --version 2>&1)"
printf "Python: %s\n" "$PY_VERSION"
case "$PY_VERSION" in
  *"Python 3.12"*) ;;
  *) warn "Expected Python 3.12.x. If backend import fails, rebuild Codespace or switch Python to 3.12.13." ;;
esac

say "Backend dependency install"
cd "$ROOT_DIR/backend"
python -m pip install --upgrade pip
pip install -r requirements.txt

say "Backend import check"
if [ -f import_all_smoke_test.py ]; then
  python import_all_smoke_test.py
else
  warn "backend/import_all_smoke_test.py missing; continuing but npm run check should add/prove this"
fi

say "Frontend dependency install"
cd "$ROOT_DIR/frontend"
npm install

say "Starting full ecosystem"
printf "Backend health: http://localhost:8000/api/health\n"
printf "Board API:       http://localhost:8000/api/v3/board\n"
printf "Frontend:        http://localhost:3000/hospital-board\n"
printf "\nOpen Codespaces PORTS -> 3000 -> Open in Browser.\n"
cd "$ROOT_DIR"
npm run dev
