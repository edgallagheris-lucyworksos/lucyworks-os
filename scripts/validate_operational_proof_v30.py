from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    target = ROOT / path
    assert target.exists(), f"missing required file: {path}"
    return target.read_text(encoding="utf-8")


models = read("apps/api/app/operational_proof_v30_models.py")
routes = read("apps/api/app/operational_proof_v30_routes.py")
connected = read("apps/api/app/connected_surfaces_v30_patch.py")
queues = read("apps/api/app/role_queue_routes.py")
readiness = read("apps/api/app/production_readiness_v30_patch.py")
installer = read("apps/api/app/critical_result_deadline_patch.py")
migration = read("apps/api/migrations/versions/0024_operational_proof_v30.py")
smoke = read("apps/api/operational_proof_v30_smoke_test.py")
authority = read("apps/api/operational_proof_v30_authority_test.py")
page = read("apps/web/app/operational-proof/page.tsx")
component = read("apps/web/components/operational-proof-v30.tsx")
system_control = read("apps/web/app/system-control/page.tsx")
runbook = read("docs/OPERATIONAL_PROOF_DEMO_HOSPITAL_V30.md")
runner = read("scripts/prove-operational-v30.sh")
package = read("package.json")
restore = read("scripts/restore-rehearsal.sh")

for model in [
    "OperationalProofRunV30",
    "OperationalProofStepV30",
    "OperationalProofScenarioV30",
    "MobileAcceptanceV30",
]:
    assert f"class {model}" in models, model

for strict_schema in ["class RunCreate", "class EpisodeAttach", "class ScenarioRecord", "class MobileAssessmentCreate", "class CompleteRun"]:
    position = routes.index(strict_schema)
    window = routes[position:position + 500]
    assert 'model_config = ConfigDict(extra="forbid")' in window, strict_schema

scenario_codes = [
    "emergency_full_schedule",
    "theatre_imaging_overrun",
    "staff_unavailable",
    "unacknowledged_handover",
    "overdue_critical_result",
    "discharge_medication_or_comms_block",
    "stale_concurrent_update",
    "duplicate_patient_identity",
]
for code in scenario_codes:
    assert f'"{code}"' in routes, code
    assert f'"{code}"' in smoke, code
assert routes.count("expectedDetection") >= 1
assert '"urgentAccessPreserved": True' in smoke
assert '"realHospitalDeploymentReady": False' in routes
assert '"passed_with_manual_boundary"' in routes
assert "physical Android" in routes
assert "real hospital OIDC" in routes

for step_code in [
    "referral", "identity", "triage", "consult", "consent", "schedule",
    "handover", "discharge", "closure", "board", "queues", "evidence",
]:
    assert f'("{step_code}",' in routes, step_code

for marker in [
    'board["canonicalEpisodes"]',
    'board["unplacedEpisodes"]',
    'board["recentCanonicalChanges"]',
    'board["connectedOperationalProofVersion"] = "v30"',
    "queue_for_role_v30",
    '"recent_completed_episodes"',
]:
    assert marker in connected, marker

for marker in [
    '"canonical_episodes"',
    '"governed_handovers"',
    '"critical_canonical_episodes"',
    '"unacknowledged_governed_handovers"',
]:
    assert marker in queues, marker

assert 'revision: str = "0024_operational_proof_v30"' in migration
assert 'down_revision: Union[str, None] = "0023_hospital_pilot_v29"' in migration
for table in [
    "OperationalProofRunV30",
    "OperationalProofStepV30",
    "OperationalProofScenarioV30",
    "MobileAcceptanceV30",
]:
    assert f"{table}.__table__.create" in migration, table

assert "V30_TABLES" in readiness
assert "V30_OPERATIONAL_PROOF_REQUIRED" in readiness
assert "operational_proof_v30_installed" in readiness
assert "production_readiness_v30_patch" in installer
assert "OperationalProofV30" in page
for control in [
    "Create proof run",
    "Attach canonical episode",
    "Evaluate referral to closure",
    "Record scenario result",
    "Test this device",
    "I personally completed the physical Android journey",
    "Complete governed proof",
    "Load evidence report",
]:
    assert control in component, control
assert '["/operational-proof", "Operational proof and demo hospital"]' in system_control
assert '"proof:v30": "bash scripts/prove-operational-v30.sh"' in package
assert "hospital_command_v9_smoke_test.py" in runner
assert "operational_proof_v30_smoke_test.py" in runner
assert "operational_proof_v30_authority_test.py" in runner
assert "npm run proof:v30" in runbook
assert "passed_with_manual_boundary" in runbook

assert "0024_operational_proof_v30" in restore
for table in [
    "operationalproofrunv30",
    "operationalproofstepv30",
    "operationalproofscenariov30",
    "mobileacceptancev30",
]:
    assert table in restore, table

for forbidden in [
    '@router.post("/prescribe',
    '@router.post("/external-write',
    '@router.post("/clinical-sign',
    'mode="production"',
    'realHospitalDeploymentReady": True',
]:
    assert forbidden not in routes, forbidden

assert "silentlyApprove" in authority
assert "urgentAccessPreserved\": False" in authority
assert "status_code == 403" in authority
assert "status_code == 422" in authority
assert "status_code == 409" in authority

print("OPERATIONAL_PROOF_V30_STATIC_VALIDATION_PASSED")
