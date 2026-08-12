#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="$HOME/.lucyworks"
SECRET_FILE="$STATE_DIR/codespace-auth-secret"
PID_DIR="/tmp/lucyworks-pids"
LOG_FILE="/tmp/lucyworks-codespace.log"
API_LOG="/tmp/lucyworks-api.log"
WEB_LOG="/tmp/lucyworks-web.log"
RUNNING_SHA_FILE="/tmp/lucyworks-running-sha"

mkdir -p "$STATE_DIR" "$PID_DIR"
cd "$ROOT"

if [[ -n "${CODESPACE_NAME:-}" && -n "${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-}" ]]; then
  WEB_URL="https://${CODESPACE_NAME}-3000.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}"
  API_URL="https://${CODESPACE_NAME}-8000.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}"
else
  WEB_URL="http://localhost:3000"
  API_URL="http://localhost:8000"
fi

print_links() {
  cat <<EOF

LucyWorks OS is running.

Login:        ${WEB_URL}/login
System control:${WEB_URL}/system-control
Patient command:${WEB_URL}/workspace
Quick input:  ${WEB_URL}/input
Hospital board:${WEB_URL}/hospital-board
Referral intake:${WEB_URL}/referral-intake
Patient care: ${WEB_URL}/care
Integrations: ${WEB_URL}/integrations
API health:   ${API_URL}/api/health

Running commit: $(cat "$RUNNING_SHA_FILE" 2>/dev/null || git rev-parse --short HEAD)

Logs:
  tail -n 100 ${API_LOG}
  tail -n 100 ${WEB_LOG}

Restart:
  bash scripts/codespace-autostart.sh
EOF
}

# Codespaces can resume with a healthy but stale server from a previous session.
# On main, safely fast-forward a clean worktree before deciding whether the
# existing processes are reusable. Never overwrite local edits or divergent work.
CURRENT_BRANCH="$(git branch --show-current 2>/dev/null || true)"
UPDATED=false
if [[ "$CURRENT_BRANCH" == "main" ]] && git remote get-url origin >/dev/null 2>&1; then
  if git fetch -q origin main; then
    LOCAL_SHA="$(git rev-parse HEAD)"
    REMOTE_SHA="$(git rev-parse origin/main)"
    if [[ "$LOCAL_SHA" != "$REMOTE_SHA" ]]; then
      if [[ -z "$(git status --porcelain)" ]] && git merge-base --is-ancestor "$LOCAL_SHA" "$REMOTE_SHA"; then
        echo "Updating Codespace from ${LOCAL_SHA:0:8} to ${REMOTE_SHA:0:8}..."
        git merge --ff-only origin/main
        UPDATED=true
      else
        echo "Codespace main is not safely fast-forwardable; leaving local work untouched." >&2
        echo "Current: ${LOCAL_SHA:0:8}  origin/main: ${REMOTE_SHA:0:8}" >&2
      fi
    fi
  else
    echo "Could not refresh origin/main; continuing with the checked-out commit." >&2
  fi
fi

CHECKED_OUT_SHA="$(git rev-parse HEAD)"
RUNNING_SHA="$(cat "$RUNNING_SHA_FILE" 2>/dev/null || true)"

# Reuse healthy servers only when they are known to be serving this exact commit.
# This prevents a resumed Codespace from silently serving an old LucyWorks build.
if [[ "$UPDATED" == false ]] \
  && [[ "$RUNNING_SHA" == "$CHECKED_OUT_SHA" ]] \
  && curl -fsS --max-time 3 http://127.0.0.1:8000/api/health >/dev/null 2>&1 \
  && curl -fsS --max-time 5 http://127.0.0.1:3000/login >/dev/null 2>&1; then
  print_links
  exit 0
fi

{
  echo "== LucyWorks OS Codespace startup =="
  echo "Root: $ROOT"
  echo "Started: $(date -Iseconds)"
  echo "Commit: $CHECKED_OUT_SHA"
  echo "Web URL: $WEB_URL"
  echo "API URL: $API_URL"
} | tee "$LOG_FILE"

# Generate one persistent signed-development-token secret per Codespace user.
if [[ ! -s "$SECRET_FILE" ]]; then
  python - <<'PY' > "$SECRET_FILE"
import secrets
print(secrets.token_hex(48))
PY
  chmod 600 "$SECRET_FILE"
fi
AUTH_SECRET="$(cat "$SECRET_FILE")"
DATABASE_URL="${DATABASE_URL:-sqlite:///$ROOT/apps/api/lucyworks.db}"

# Remove stale listeners that otherwise produce blank previews, 502 errors, or
# an apparently healthy server running an older checkout.
for port in 3000 8000; do
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${port}/tcp" >> "$LOG_FILE" 2>&1 || true
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -ti tcp:"$port" | xargs -r kill -9 >> "$LOG_FILE" 2>&1 || true
  fi
done

rm -f "$PID_DIR/api.pid" "$PID_DIR/web.pid" "$RUNNING_SHA_FILE"

# Keep dependency installation deterministic while allowing repeat starts.
echo "Installing API dependencies..." | tee -a "$LOG_FILE"
(
  cd "$ROOT/apps/api"
  python -m pip install -q -r requirements.txt
) >> "$API_LOG" 2>&1

echo "Installing web dependencies..." | tee -a "$LOG_FILE"
(
  cd "$ROOT/apps/web"
  npm install --no-audit --no-fund
) >> "$WEB_LOG" 2>&1

# Start the API with signed local development login. These defaults are only
# used inside the Codespace runner and are not production deployment settings.
(
  cd "$ROOT/apps/api"
  exec env \
    DATABASE_URL="$DATABASE_URL" \
    AUTO_CREATE_SCHEMA=true \
    AUTH_MODE=local \
    AUTH_ENFORCEMENT=required \
    AUTH_DEV_LOGIN_ENABLED=true \
    AUTH_JWT_SECRET="$AUTH_SECRET" \
    AUTH_ISSUER=lucyworks-codespace \
    AUTH_AUDIENCE=lucyworks-api \
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
) > "$API_LOG" 2>&1 &
API_PID=$!
echo "$API_PID" > "$PID_DIR/api.pid"

# Browser calls remain same-origin on port 3000. Next.js proxies /api to the
# private API process on 127.0.0.1:8000, avoiding Codespaces cross-origin and
# private-port authentication problems.
(
  cd "$ROOT/apps/web"
  exec env \
    API_INTERNAL_BASE=http://127.0.0.1:8000 \
    NEXT_PUBLIC_API_BASE="$WEB_URL" \
    npm run dev -- --hostname 0.0.0.0 --port 3000
) > "$WEB_LOG" 2>&1 &
WEB_PID=$!
echo "$WEB_PID" > "$PID_DIR/web.pid"

# Wait for both services and fail with useful logs rather than a blank preview.
api_ready=false
web_ready=false
for _ in $(seq 1 90); do
  if curl -fsS --max-time 3 http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
    api_ready=true
  fi
  if curl -fsS --max-time 5 http://127.0.0.1:3000/login >/dev/null 2>&1; then
    web_ready=true
  fi
  if [[ "$api_ready" == true && "$web_ready" == true ]]; then
    break
  fi
  sleep 2
done

if [[ "$api_ready" != true ]]; then
  echo "LucyWorks API did not start. Last API log lines:" >&2
  tail -n 100 "$API_LOG" >&2 || true
  exit 1
fi

if [[ "$web_ready" != true ]]; then
  echo "LucyWorks web application did not start. Last web log lines:" >&2
  tail -n 100 "$WEB_LOG" >&2 || true
  exit 1
fi

printf '%s\n' "$CHECKED_OUT_SHA" > "$RUNNING_SHA_FILE"
print_links
