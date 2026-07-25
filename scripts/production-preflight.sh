#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$ROOT/deploy"
ENV_FILE="${1:-$DEPLOY_DIR/.env.production}"
COMPOSE_FILE="$DEPLOY_DIR/docker-compose.production.yml"

fail() { echo "PRE-FLIGHT FAILED: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

command -v docker >/dev/null 2>&1 || fail "docker is not installed"
docker compose version >/dev/null 2>&1 || fail "docker compose is not available"
[[ -f "$ENV_FILE" ]] || fail "missing $ENV_FILE; copy deploy/production.env.template and complete it"

if grep -Eq '(^|=)REQUIRED_' "$ENV_FILE"; then
  fail "production environment still contains REQUIRED placeholders"
fi

required=(PUBLIC_DOMAIN POSTGRES_PASSWORD AUTH_MODE AUTH_ENFORCEMENT AUTH_DEV_LOGIN_ENABLED AUTH_RETURN_BEARER_DEV AUTH_SESSION_MINUTES AUTH_IDLE_MINUTES OIDC_ISSUER OIDC_JWKS_URL OIDC_AUTHORIZATION_URL OIDC_TOKEN_URL OIDC_CLIENT_ID OIDC_CLIENT_SECRET AUTH_ROLE_MAP METRICS_API_KEY LEGACY_WRITE_MODE)
for key in "${required[@]}"; do
  value="$(grep -E "^${key}=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- || true)"
  [[ -n "$value" ]] || fail "$key is empty or missing"
done

[[ "$(grep '^AUTH_MODE=' "$ENV_FILE" | cut -d= -f2-)" == "oidc" ]] || fail "AUTH_MODE must be oidc"
[[ "$(grep '^AUTH_ENFORCEMENT=' "$ENV_FILE" | cut -d= -f2-)" == "required" ]] || fail "AUTH_ENFORCEMENT must be required"
[[ "$(grep '^AUTH_DEV_LOGIN_ENABLED=' "$ENV_FILE" | cut -d= -f2-)" == "false" ]] || fail "AUTH_DEV_LOGIN_ENABLED must be false"
[[ "$(grep '^AUTH_RETURN_BEARER_DEV=' "$ENV_FILE" | cut -d= -f2-)" == "false" ]] || fail "browser bearer return must be disabled"
[[ "$(grep '^AUTO_CREATE_SCHEMA=' "$ENV_FILE" | cut -d= -f2-)" == "false" ]] || fail "AUTO_CREATE_SCHEMA must be false"
[[ "$(grep '^LEGACY_WRITE_MODE=' "$ENV_FILE" | cut -d= -f2-)" == "block" ]] || fail "LEGACY_WRITE_MODE must be block"
[[ "$(grep '^LUCYWORKS_LEGACY_TEST_BYPASS=' "$ENV_FILE" | cut -d= -f2-)" == "false" ]] || fail "legacy test bypass must be false"

session_minutes="$(grep '^AUTH_SESSION_MINUTES=' "$ENV_FILE" | cut -d= -f2-)"
idle_minutes="$(grep '^AUTH_IDLE_MINUTES=' "$ENV_FILE" | cut -d= -f2-)"
[[ "$session_minutes" =~ ^[0-9]+$ && "$session_minutes" -ge 15 && "$session_minutes" -le 1440 ]] || fail "AUTH_SESSION_MINUTES must be between 15 and 1440"
[[ "$idle_minutes" =~ ^[0-9]+$ && "$idle_minutes" -ge 5 && "$idle_minutes" -le 120 ]] || fail "AUTH_IDLE_MINUTES must be between 5 and 120"
[[ "$idle_minutes" -lt "$session_minutes" ]] || fail "idle timeout must be shorter than absolute session lifetime"

for key in POSTGRES_PASSWORD OIDC_CLIENT_SECRET PIMS_WEBHOOK_SECRET IMAGING_WEBHOOK_SECRET LAB_WEBHOOK_SECRET HR_WEBHOOK_SECRET METRICS_API_KEY; do
  value="$(grep -E "^${key}=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- || true)"
  [[ ${#value} -ge 20 ]] || fail "$key must be at least 20 characters"
done

PUBLIC_DOMAIN="$(grep '^PUBLIC_DOMAIN=' "$ENV_FILE" | cut -d= -f2-)"
[[ "$PUBLIC_DOMAIN" != "localhost" && "$PUBLIC_DOMAIN" == *.* ]] || fail "PUBLIC_DOMAIN must be a real DNS name"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config >/tmp/lucyworks-compose-rendered.yml
pass "Docker Compose configuration renders"
pass "production OIDC and secure browser session policy is enforced"
pass "browser bearer return and development login are disabled"
pass "legacy unsafe writes are blocked"
pass "required secrets are present and non-trivial"
pass "public DNS name is configured"

echo "Production preflight completed. This validates configuration, not hospital approval or live-service authorisation."
