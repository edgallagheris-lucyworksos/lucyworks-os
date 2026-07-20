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

required=(PUBLIC_DOMAIN POSTGRES_PASSWORD AUTH_MODE AUTH_ENFORCEMENT AUTH_DEV_LOGIN_ENABLED OIDC_ISSUER OIDC_JWKS_URL OIDC_AUTHORIZATION_URL OIDC_TOKEN_URL OIDC_CLIENT_ID OIDC_CLIENT_SECRET AUTH_ROLE_MAP)
for key in "${required[@]}"; do
  value="$(grep -E "^${key}=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- || true)"
  [[ -n "$value" ]] || fail "$key is empty or missing"
done

[[ "$(grep '^AUTH_MODE=' "$ENV_FILE" | cut -d= -f2-)" == "oidc" ]] || fail "AUTH_MODE must be oidc"
[[ "$(grep '^AUTH_ENFORCEMENT=' "$ENV_FILE" | cut -d= -f2-)" == "required" ]] || fail "AUTH_ENFORCEMENT must be required"
[[ "$(grep '^AUTH_DEV_LOGIN_ENABLED=' "$ENV_FILE" | cut -d= -f2-)" == "false" ]] || fail "AUTH_DEV_LOGIN_ENABLED must be false"
[[ "$(grep '^AUTO_CREATE_SCHEMA=' "$ENV_FILE" | cut -d= -f2-)" == "false" ]] || fail "AUTO_CREATE_SCHEMA must be false"
[[ "$(grep '^LUCYWORKS_LEGACY_TEST_BYPASS=' "$ENV_FILE" | cut -d= -f2-)" == "false" ]] || fail "legacy test bypass must be false"

for key in POSTGRES_PASSWORD OIDC_CLIENT_SECRET PIMS_WEBHOOK_SECRET IMAGING_WEBHOOK_SECRET LAB_WEBHOOK_SECRET HR_WEBHOOK_SECRET; do
  value="$(grep -E "^${key}=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- || true)"
  [[ ${#value} -ge 20 ]] || fail "$key must be at least 20 characters"
done

PUBLIC_DOMAIN="$(grep '^PUBLIC_DOMAIN=' "$ENV_FILE" | cut -d= -f2-)"
[[ "$PUBLIC_DOMAIN" != "localhost" && "$PUBLIC_DOMAIN" == *.* ]] || fail "PUBLIC_DOMAIN must be a real DNS name"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config >/tmp/lucyworks-compose-rendered.yml
pass "Docker Compose configuration renders"
pass "production identity policy is enforced"
pass "development and legacy bypasses are disabled"
pass "required secrets are present and non-trivial"
pass "public DNS name is configured"

echo "Production preflight completed. This validates configuration, not hospital approval or live-service authorisation."
