#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "== LucyWorksOS: one-command hospital system runner =="

echo "\n== Pull latest code =="
git pull --ff-only || true

echo "\n== Start full ecosystem =="
npm run dev
