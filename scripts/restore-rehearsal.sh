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
expected_version="$(cd "$ROOT/apps/api" && python - <<'PY'
from alembic.config import Config
from alembic.script import ScriptDirectory
head = ScriptDirectory.from_config(Config('alembic.ini')).get_current_head()
if not head:
    raise SystemExit('Alembic has no current head')
print(head)
PY
)"
[[ "$version" == "$expected_version" ]] || { echo "restored migration version is $version, expected current head $expected_version" >&2; exit 1; }

# Critical durable tables. Keep this list focused on cross-cutting records that
# must survive a restore; migration-head validation proves the full schema level.
for table in \
  evidenceevent canonicalepisodestate authsession durableevent \
  patientclinicalrecordv8 referralintakev9 consentauthorisationv9 episodehandoverv9 \
  safetycasev10 referralidentityintakev12 speechcapturev19 speechdraftv19 \
  canonicalcommandv26 configurationreleasev27 speechsessionv28 integrationeventv28 \
  hospitalpilotv29 operationalproofrunv30 \
  servicepricev32 regulatedestimatev32 aiprovenancerecordv32 \
  chargeprovenancev32 complaintrecordv32 prescriptionchoicev32; do
  exists="$("${COMPOSE[@]}" exec -T postgres psql -U "$POSTGRES_USER" -d "$TEST_DB" -Atc "select to_regclass('public.$table') is not null")"
  [[ "$exists" == "t" ]] || { echo "restored critical table missing: $table" >&2; exit 1; }
done

counts="$("${COMPOSE[@]}" exec -T postgres psql -U "$POSTGRES_USER" -d "$TEST_DB" -Atc 'select json_build_object(
  '"'"'evidence'"'"', (select count(*) from evidenceevent),
  '"'"'patients'"'"', (select count(*) from patientclinicalrecordv8),
  '"'"'canonicalEpisodes'"'"', (select count(*) from canonicalepisodestate),
  '"'"'configurationReleases'"'"', (select count(*) from configurationreleasev27),
  '"'"'speechSessions'"'"', (select count(*) from speechsessionv28),
  '"'"'integrationEvents'"'"', (select count(*) from integrationeventv28),
  '"'"'hospitalPilots'"'"', (select count(*) from hospitalpilotv29),
  '"'"'operationalProofRuns'"'"', (select count(*) from operationalproofrunv30),
  '"'"'regulatedEstimates'"'"', (select count(*) from regulatedestimatev32),
  '"'"'aiProvenanceRecords'"'"', (select count(*) from aiprovenancerecordv32),
  '"'"'chargeRecords'"'"', (select count(*) from chargeprovenancev32),
  '"'"'complaints'"'"', (select count(*) from complaintrecordv32),
  '"'"'prescriptionChoices'"'"', (select count(*) from prescriptionchoicev32)
)')"

echo "Restore rehearsal passed for $BACKUP_NAME at migration $version"
echo "Restored integrity sample: $counts"