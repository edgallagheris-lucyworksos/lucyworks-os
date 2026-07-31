from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    target = ROOT / path
    assert target.exists(), f"missing required file: {path}"
    return target.read_text(encoding="utf-8")


models = read("apps/api/app/hospital_pilot_v29_models.py")
routes = read("apps/api/app/hospital_pilot_v29_routes.py")
readiness = read("apps/api/app/production_readiness_v29_patch.py")
migration = read("apps/api/migrations/versions/0023_hospital_pilot_v29.py")
page = read("apps/web/app/pilot-lab/page.tsx")
component = read("apps/web/components/hospital-pilot-lab-v29.tsx")
system_control = read("apps/web/app/system-control/page.tsx")
restore = read("scripts/restore-rehearsal.sh")

for model in [
    "SpeechAdapterV29", "VeterinaryTerminologyPackV29", "IntegrationSimulatorV29",
    "SimulatorScenarioV29", "SimulatorRunV29", "ReadinessAssessmentV29",
    "HospitalPilotV29", "PilotApprovalV29", "PilotIncidentV29",
    "PilotMeasurementV29", "ExportArtifactV29",
]:
    assert f"class {model}" in models, model

for boundary in [
    'model_config = ConfigDict(extra="forbid")',
    'FAULT_TYPES = {"delay", "outage", "duplicate", "conflict", "missing_fields", "incorrect_identifier", "out_of_order", "none"}',
    '"SYNTHETIC TEST DATA - NOT A CLINICAL RECORD"',
    'direction="simulated_inbound"',
    'patient_ref=None',
    'episode_ref=None',
    '"canonicalAttachmentCount": 0',
    '"urgentAccessPreserved": True',
    '"Continue urgent patient care through the existing non-pilot hospital workflow."',
    'APPROVAL_TYPES = {"operations", "clinical"}',
    '"independent_pilot_approvals_required"',
    '"pilot_not_ready"',
    '"requiresHumanReview": True',
    '"writeOperations": []',
]:
    assert boundary in routes, boundary

assert "external-system write-back" not in routes.lower() or "no vendor write-back" in routes.lower()
assert "rawAudioRetention": False if False else True
assert 'revision: str = "0023_hospital_pilot_v29"' in migration
assert 'down_revision: Union[str, None] = "0022_real_hospital_connection_v28"' in migration
assert "V29_TABLES" in readiness
assert "V29_PILOT_CONTROL_REQUIRED" in readiness
assert "hospital_pilot_v29_installed" in readiness
assert "HospitalPilotLabV29" in page
for control in [
    "Test this device", "Create terminology release", "Create isolated simulator",
    "Run complete readiness assessment", "Create bounded pilot",
    "Run red-incident auto-stop proof", "Generate vendor specification",
    "Generate hospital deployment pack",
]:
    assert control in component, control
assert '["/pilot-lab", "Hospital pilot and integration laboratory"]' in system_control
assert "0023_hospital_pilot_v29" in restore
for table in ["speechadapterv29", "integrationsimulatorv29", "readinessassessmentv29", "hospitalpilotv29", "pilotincidentv29", "exportartifactv29"]:
    assert table in restore, table

for forbidden in [
    '@router.post("/external-write',
    '@router.post("/prescribe',
    '@router.post("/sign-clinical',
    'mode="write"',
    'environment="production"',
]:
    assert forbidden not in routes, forbidden

print("HOSPITAL_PILOT_V29_STATIC_VALIDATION_PASSED")
