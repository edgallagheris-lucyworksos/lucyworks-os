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
[[ "$version" == "0013_medication_v18" ]] || { echo "restored migration version is $version, expected 0013_medication_v18" >&2; exit 1; }

for table in \
  evidenceevent operationalblock canonicalepisodestate readinesscontrol pilotrun \
  hospitalconfigurationrecord configurationverificationtask workforceprofile workforcecompetency \
  workforceshiftv6 workforceavailabilityexceptionv6 referralintake historicalreplayrun \
  authsession durableevent eventacknowledgement canonicalshadowcomparison integrationretryjob \
  medicationorder medicationadministration anaesthesiarecord clinicalobservation treatmenttask \
  controlleddrugledgerentry inventoryitem inventorymovement diagnosticworkitem samplechainevent dischargeplan \
  owneraccountv8 patientclinicalrecordv8 patientownerlinkv8 patientproblemv8 patientallergyv8 patientweightv8 \
  clinicalencounterv8 clinicalnotev8 formularymedicinev8 formularydoserulev8 medicationsafetyreviewv8 \
  anaesthesiachartv8 anaesthesiaobservationv8 anaesthesiadrugeventv8 fluidplanv8 fluidbalanceentryv8 \
  inpatientcareplanv8 inpatientchartentryv8 procedurerecordv8 implanttracev8 estimatev8 estimatelinev8 \
  insurancecasev8 financialtransactionv8 communicationeventv8 clinicaldocumentv8 \
  referralintakev9 consentauthorisationv9 episodehandoverv9 episodecheckpointv9 episodetransitionv9 episodeclosurev9 \
  safetycasev10 safetyhazardv10 safetyreviewv10 deploymentprofilev10 \
  referralidentityintakev12 identitymatchreviewv12 referraldocumentv12 referraltriagev12 accessreviewv12 \
  productimportbatchv18 veterinaryproductv18 medicationprotocolv18 dosecalculationv18 medicationproposalv18; do
  exists="$("${COMPOSE[@]}" exec -T postgres psql -U "$POSTGRES_USER" -d "$TEST_DB" -Atc "select to_regclass('public.$table') is not null")"
  [[ "$exists" == "t" ]] || { echo "restored table missing: $table" >&2; exit 1; }
done

counts="$("${COMPOSE[@]}" exec -T postgres psql -U "$POSTGRES_USER" -d "$TEST_DB" -Atc 'select json_build_object(
  '"'"'evidence'"'"', (select count(*) from evidenceevent),
  '"'"'configuration'"'"', (select count(*) from hospitalconfigurationrecord),
  '"'"'workforce'"'"', (select count(*) from workforceprofile),
  '"'"'referrals'"'"', (select count(*) from referralintake),
  '"'"'durableEvents'"'"', (select count(*) from durableevent),
  '"'"'medicationOrders'"'"', (select count(*) from medicationorder),
  '"'"'patients'"'"', (select count(*) from patientclinicalrecordv8),
  '"'"'encounters'"'"', (select count(*) from clinicalencounterv8),
  '"'"'anaesthesiaCharts'"'"', (select count(*) from anaesthesiachartv8),
  '"'"'procedures'"'"', (select count(*) from procedurerecordv8),
  '"'"'estimates'"'"', (select count(*) from estimatev8),
  '"'"'communications'"'"', (select count(*) from communicationeventv8),
  '"'"'documents'"'"', (select count(*) from clinicaldocumentv8),
  '"'"'commandReferrals'"'"', (select count(*) from referralintakev9),
  '"'"'consents'"'"', (select count(*) from consentauthorisationv9),
  '"'"'handovers'"'"', (select count(*) from episodehandoverv9),
  '"'"'transitions'"'"', (select count(*) from episodetransitionv9),
  '"'"'closures'"'"', (select count(*) from episodeclosurev9),
  '"'"'safetyCases'"'"', (select count(*) from safetycasev10),
  '"'"'hazards'"'"', (select count(*) from safetyhazardv10),
  '"'"'safetyReviews'"'"', (select count(*) from safetyreviewv10),
  '"'"'deploymentProfiles'"'"', (select count(*) from deploymentprofilev10),
  '"'"'identityIntakes'"'"', (select count(*) from referralidentityintakev12),
  '"'"'identityReviews'"'"', (select count(*) from identitymatchreviewv12),
  '"'"'referralDocuments'"'"', (select count(*) from referraldocumentv12),
  '"'"'triageRecords'"'"', (select count(*) from referraltriagev12),
  '"'"'accessReviews'"'"', (select count(*) from accessreviewv12),
  '"'"'productImports'"'"', (select count(*) from productimportbatchv18),
  '"'"'veterinaryProducts'"'"', (select count(*) from veterinaryproductv18),
  '"'"'medicationProtocols'"'"', (select count(*) from medicationprotocolv18),
  '"'"'doseCalculations'"'"', (select count(*) from dosecalculationv18),
  '"'"'medicationProposals'"'"', (select count(*) from medicationproposalv18)
)')"
echo "Restore rehearsal passed for $BACKUP_NAME at migration $version"
echo "Restored integrity sample: $counts"
