#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$ROOT/deploy"
ENV_FILE="${1:-$DEPLOY_DIR/.env.production}"
BASE_URL="${LUCYWORKS_BASE_URL:-https://${PUBLIC_DOMAIN:-}}"

[[ "${LUCYWORKS_FAILURE_DRILL_CONFIRMATION:-}" == "RUN CONTROLLED DRILL" ]] || {
  echo 'Set LUCYWORKS_FAILURE_DRILL_CONFIRMATION="RUN CONTROLLED DRILL".' >&2
  exit 1
}
[[ -f "$ENV_FILE" ]] || { echo "missing $ENV_FILE" >&2; exit 1; }
[[ -n "$BASE_URL" && "$BASE_URL" != "https://" ]] || { echo "set LUCYWORKS_BASE_URL or PUBLIC_DOMAIN" >&2; exit 1; }

COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$DEPLOY_DIR/docker-compose.production.yml")
COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT

health() {
  curl --fail --silent --show-error "$BASE_URL/api/health/ready"
}

health >/dev/null
echo "Pre-drill readiness passed"

# This drill requires a controlled local/development login account. OIDC-backed
# production drills should supply a short-lived session cookie through the
# organisation's approved test harness instead of embedding credentials here.
USER_ID="${LUCYWORKS_DRILL_USER_ID:-1}"
curl --fail --silent --show-error -c "$COOKIE_JAR" -b "$COOKIE_JAR" \
  -H 'Content-Type: application/json' \
  -d "{\"user_id\":$USER_ID}" \
  "$BASE_URL/api/auth/dev-login" >/tmp/lucyworks-drill-login.json

CSRF="$(awk '$6 == "lucyworks_csrf" {print $7}' "$COOKIE_JAR" | tail -1)"
[[ -n "$CSRF" ]] || { echo "CSRF cookie not issued" >&2; exit 1; }

before="$(curl --fail --silent --show-error -b "$COOKIE_JAR" "$BASE_URL/api/v7/events?after_sequence=0&limit=1000")"
before_sequence="$(python -c 'import json,sys; print(json.load(sys.stdin).get("nextSequence",0))' <<<"$before")"

curl --fail --silent --show-error -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
  -H "X-CSRF-Token: $CSRF" -H 'Content-Type: application/json' \
  -d "{\"event_type\":\"failure_drill_checkpoint\",\"aggregate_type\":\"failure_drill\",\"aggregate_ref\":\"api-restart\",\"payload\":{\"synthetic\":true},\"idempotency_key\":\"failure-drill-$before_sequence\"}" \
  "$BASE_URL/api/v7/events" >/tmp/lucyworks-drill-event.json

checkpoint="$(python -c 'import json,sys; print(json.load(sys.stdin)["event"]["sequence"])' </tmp/lucyworks-drill-event.json)"
echo "Durable checkpoint sequence $checkpoint created"

"${COMPOSE[@]}" restart api

for _ in $(seq 1 60); do
  if health >/dev/null 2>&1; then break; fi
  sleep 2
done
health >/dev/null || { echo "API did not recover within the drill window" >&2; exit 1; }

after="$(curl --fail --silent --show-error -b "$COOKIE_JAR" "$BASE_URL/api/v7/events?after_sequence=$before_sequence&limit=100")"
python - "$checkpoint" <<'PY' <<<"$after"
import json, sys
expected = int(sys.argv[1])
payload = json.load(sys.stdin)
sequences = [row["sequence"] for row in payload.get("events", [])]
assert expected in sequences, (expected, sequences)
print("Durable event replay after API restart passed", expected)
PY

echo "Controlled v7 API restart and event-recovery drill passed"
