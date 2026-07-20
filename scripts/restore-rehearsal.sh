#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$ROOT/deploy"
ENV_FILE="${1:-$DEPLOY_DIR/.env.production}"
BACKUP_FILE="${2:-}"

[[ "${LUCYWORKS_RESTORE_CONFIRMATION:-}" == "REHEARSE RESTORE" ]] || {
  echo 'Set LUCYWORKS_RESTORE_CONFIRMATION="REHEARSE RESTORE" for an isolated restore rehearsal.' >&2
  exit 1
}
[[ -f "$ENV_FILE" ]] || { echo "missing $ENV_FILE" >&2; exit 1; }
[[ -n "$BACKUP_FILE" && -f "$BACKUP_FILE" ]] || { echo "provide a valid backup file as argument 2" >&2; exit 1; }
[[ -f "$BACKUP_FILE.sha256" ]] || { echo "missing checksum $BACKUP_FILE.sha256" >&2; exit 1; }
(cd "$(dirname "$BACKUP_FILE")" && sha256sum -c "$(basename "$BACKUP_FILE").sha256")

POSTGRES_USER="$(grep '^POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2-)"
POSTGRES_DB="$(grep '^POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2-)"
POSTGRES_USER="${POSTGRES_USER:-lucyworks}"
POSTGRES_DB="${POSTGRES_DB:-lucyworks}"
TEST_DB="lucyworks_restore_$RANDOM$RANDOM"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$DEPLOY_DIR/docker-compose.production.yml")

case "$(realpath "$BACKUP_FILE")" in
  "$(realpath "$DEPLOY_DIR/backups")"/*) ;;
  *) echo "backup must be inside deploy/backups so the database container can read it" >&2; exit 1 ;;
esac
BACKUP_NAME="$(basename "$BACKUP_FILE")"

cleanup() {
  "${COMPOSE[@]}" exec -T postgres dropdb -U "$POSTGRES_USER" --if-exists "$TEST_DB" >/dev/null 2>&1 || true
}
trap cleanup EXIT

"${COMPOSE[@]}" up -d postgres
"${COMPOSE[@]}" exec -T postgres createdb -U "$POSTGRES_USER" "$TEST_DB"
"${COMPOSE[@]}" exec -T postgres pg_restore -U "$POSTGRES_USER" -d "$TEST_DB" --clean --if-exists --no-owner "/backups/$BACKUP_NAME"

version="$("${COMPOSE[@]}" exec -T postgres psql -U "$POSTGRES_USER" -d "$TEST_DB" -Atc 'select version_num from alembic_version')"
[[ "$version" == "0006_production_readiness" ]] || { echo "restored migration version is $version, expected 0006_production_readiness" >&2; exit 1; }

for table in evidenceevent operationalblock canonicalepisodestate readinesscontrol pilotrun; do
  exists="$("${COMPOSE[@]}" exec -T postgres psql -U "$POSTGRES_USER" -d "$TEST_DB" -Atc "select to_regclass('public.$table') is not null")"
  [[ "$exists" == "t" ]] || { echo "restored table missing: $table" >&2; exit 1; }
done

counts="$("${COMPOSE[@]}" exec -T postgres psql -U "$POSTGRES_USER" -d "$TEST_DB" -Atc 'select json_build_object('"'"'evidence'"'"', count(*)) from evidenceevent')"
echo "Restore rehearsal passed for $BACKUP_NAME at migration $version"
echo "Restored integrity sample: $counts"
