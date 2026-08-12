#!/usr/bin/env bash
set -euo pipefail

SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/codespace-autostart.sh"

bash -n "$SCRIPT"

grep -q 'git fetch -q origin main' "$SCRIPT"
grep -q 'git merge --ff-only origin/main' "$SCRIPT"
grep -q 'RUNNING_SHA_FILE="/tmp/lucyworks-running-sha"' "$SCRIPT"
grep -q 'RUNNING_SHA.*CHECKED_OUT_SHA' "$SCRIPT"
grep -q 'printf.*CHECKED_OUT_SHA.*RUNNING_SHA_FILE' "$SCRIPT"

echo "CODESPACE_AUTOSTART_SMOKE_OK"
