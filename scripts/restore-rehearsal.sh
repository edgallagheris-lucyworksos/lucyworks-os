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
[[ "$version" == "0023_hospital_pilot_v29" ]] || { echo "restored migration version is $version, expected 0023_hospital_pilot_v29" >&2; exit 1; }

# Every governed table remains explicit here so a restore cannot pass merely
# because the database starts. This is the durable evidence surface through v29.
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
  productimportbatchv18 veterinaryproductv18 medicationprotocolv18 dosecalculationv18 medicationproposalv18 \
  speechcapturev19 speechdraftv19 speechphrasepackv19 automationdecisionv20 \
  automationruntimeconfigv22 automationtriggerv22 automationoperatoractionv23 \
  pilotauthorityv24 pilotapprovalv24 pilotcontrolactionv24 pilotshadowcomparisonv24 pilotuatscenariov24 \
  safetyrecordv25 safetyactionv25 safetydecisionv25 safetylinkv25 safetyescalationv25 safetyaccesseventv25 \
  organisationv26 sitev26 sitemembershipv26 activeoperatingcontextv26 contextswitchevidencev26 \
  canonicalcommandv26 legacyrouteconvergencev26 operationalimpactv26 \
  onboardingorganisationv27 onboardingsitev27 onboardingdepartmentv27 onboardingservicev27 \
  onboardingroomv27 onboardingequipmentv27 staffimportbatchv27 onboardingstaffv27 \
  staffcredentialv27 staffcompetencyv27 staffaccessapprovalv27 sitepolicyv27 \
  configurationreleasev27 configurationchangev27 \
  speechproviderv28 speechsessionv28 speechsegmentv28 integrationconnectorv28 \
  integrationpromotionv28 integrationeventv28 reconciliationitemv28 \
  speechadapterv29 veterinaryterminologypackv29 integrationsimulatorv29 \
  simulatorscenariov29 simulatorrunv29 readinessassessmentv29 hospitalpilotv29 \
  pilotapprovalv29 pilotincidentv29 pilotmeasurementv29 exportartifactv29; do
  exists="$("${COMPOSE[@]}" exec -T postgres psql -U "$POSTGRES_USER" -d "$TEST_DB" -Atc "select to_regclass('public.$table') is not null")"
  [[ "$exists" == "t" ]] || { echo "restored table missing: $table" >&2; exit 1; }
done

counts="$("${COMPOSE[@]}" exec -T postgres psql -U "$POSTGRES_USER" -d "$TEST_DB" -Atc 'select json_build_object(
  '"'"'evidence'"'"', (select count(*) from evidenceevent),
  '"'"'patients'"'"', (select count(*) from patientclinicalrecordv8),
  '"'"'canonicalEpisodes'"'"', (select count(*) from canonicalepisodestate),
  '"'"'configurationReleases'"'"', (select count(*) from configurationreleasev27),
  '"'"'speechSessionsV28'"'"', (select count(*) from speechsessionv28),
  '"'"'integrationEventsV28'"'"', (select count(*) from integrationeventv28),
  '"'"'speechAdaptersV29'"'"', (select count(*) from speechadapterv29),
  '"'"'terminologyPacksV29'"'"', (select count(*) from veterinaryterminologypackv29),
  '"'"'simulatorRunsV29'"'"', (select count(*) from simulatorrunv29),
  '"'"'readinessAssessmentsV29'"'"', (select count(*) from readinessassessmentv29),
  '"'"'hospitalPilotsV29'"'"', (select count(*) from hospitalpilotv29),
  '"'"'pilotIncidentsV29'"'"', (select count(*) from pilotincidentv29),
  '"'"'pilotMeasurementsV29'"'"', (select count(*) from pilotmeasurementv29),
  '"'"'deploymentArtifactsV29'"'"', (select count(*) from exportartifactv29)
)')"

echo "Restore rehearsal passed for $BACKUP_NAME at migration $version"
echo "Restored integrity sample: $counts"
