#!/usr/bin/env bash
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "Checked out: $(git rev-parse --short HEAD)"
echo "Running:     $(cat /tmp/lucyworks-running-sha 2>/dev/null || echo unknown)"
