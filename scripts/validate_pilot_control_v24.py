from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "apps/api/app/pilot_control_v24_models.py"
SERVICE = ROOT / "apps/api/app/pilot_control_v24_service.py"
ROUTES = ROOT / "apps/api/app/pilot_control_v24_routes.py"
READINESS_PATCH = ROOT / "apps/api/app/production_readiness_migration_head_v24_patch.py"
MAIN = ROOT / "apps/api/app/main.py"
MIGRATION = ROOT / "apps/api/migrations/versions/0018_bounded_pilot_control_v24.py"
SMOKE = ROOT / "apps/api/pilot_control_v24_smoke_test.py"
RUNNER = ROOT / "apps/api/pilot_control_v24_smoke_runner.py"
PAGE = ROOT / "apps/web/app/pilot-control/page.tsx"
UI = ROOT / "apps/web/components/bounded-pilot-control-v24.tsx"
SYSTEM_CONTROL = ROOT / "apps/web/app/system-control/page.tsx"

for path in (MODELS, SERVICE, ROUTES, READINESS_PATCH, MAIN, MIGRATION, SMOKE, RUNNER, PAGE, UI, SYSTEM_CONTROL):
    assert path.exists(), f"missing v24 artifact: {path}"

models_text = MODELS.read_text()
service_text = SERVICE.read_text()
routes_text = ROUTES.read_text()
patch_text = READINESS_PATCH.read_text()
main_text = MAIN.read_text()
migration_text = MIGRATION.read_text()
smoke_text = SMOKE.read_text()
runner_text = RUNNER.read_text()
ui_text = UI.read_text()
system_text = SYSTEM_CONTROL.read_text()

for token in (
    "PilotAuthorityV24", "PilotApprovalV24", "PilotControlActionV24",
    "PilotShadowComparisonV24", "PilotUATScenarioV24", "plan_version",
    "rollback_plan", "stop_criteria", "automation_mode",
    "accountable_owner_subject", "clinical_owner_subject",
):
    assert token in models_text, f"v24 model control missing: {token}"

for token in (
    "SUPPORTED_PILOT_MODES", "PILOT_ACKNOWLEDGEMENTS",
    "AUTHORISE BOUNDED LIVE PILOT WITH HUMAN CLINICAL AUTHORITY",
    "APPROVE PILOT CONTROL BOUNDARY", "INITIATE PILOT ROLLBACK",
    "record_approval", "independent_approval_missing", "clinical_owner_missing",
    "uat_incomplete", "open_red_observations", "red_shadow_mismatches",
    "automation_mode_mismatch", "stop_authority", "rollback_authority",
    "create_evidence_event",
):
    assert token in service_text, f"v24 authority control missing: {token}"

for token in (
    'prefix="/api/v24/pilots"', "canonical_pilot_route_required",
    "legacy_shadow_guard_router", '@router.post("/{authority_ref}/stop")',
    "Depends(require_authenticated)", '@router.post("/{authority_ref}/rollback")',
    "ConfigDict(extra=\"forbid\")",
):
    assert token in routes_text, f"v24 route control missing: {token}"

assert main_text.index("app.include_router(pilot_control_legacy_shadow_guard_v24_router)") < main_text.index(
    "app.include_router(shadow_mode_router)"
)
assert "app.include_router(pilot_control_v24_router)" in main_text
assert "production_readiness_migration_head_v24_patch" in main_text

for forbidden in (
    "MedicationOrder(", "MedicationAdministration(", "ClinicalNoteV8(",
    "EpisodeTransitionV9(", "EpisodeClosureV9(", ".phase =",
    '.status = "acknowledged"', '.status = "discharged"', ".status = 'discharged'",
):
    assert forbidden not in service_text + routes_text, f"v24 performs forbidden clinical action: {forbidden}"

constructed: set[str] = set()
for text in (service_text, routes_text):
    tree = ast.parse(text)
    constructed |= {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
assert not (constructed & {"MedicationOrder", "MedicationAdministration", "ClinicalNoteV8", "EpisodeTransitionV9", "EpisodeClosureV9"})

assert "ScriptDirectory.from_config" in patch_text
assert '"0006_production_readiness"' not in patch_text
assert "EXPECTED_MIGRATION_HEAD" in patch_text
assert "pilotauthorityv24" in patch_text
assert 'revision: str = "0018_bounded_pilot_control_v24"' in migration_text
assert 'down_revision: Union[str, None] = "0017_automation_operator_control_v23"' in migration_text
for table in (
    "PilotAuthorityV24.__table__.create", "PilotApprovalV24.__table__.create",
    "PilotControlActionV24.__table__.create", "PilotShadowComparisonV24.__table__.create",
    "PilotUATScenarioV24.__table__.create",
):
    assert table in migration_text, f"v24 migration missing: {table}"

for proof in (
    "canonical_pilot_route_required", "stale_pilot_authority", "planVersion",
    "patient_identity_mismatch", '"severity": "red"', "pilotStopped",
    "AUTHORISE SHADOW MODE ONLY", "AUTHORISE BOUNDED LIVE PILOT WITH HUMAN CLINICAL AUTHORITY",
    "INITIATE PILOT ROLLBACK", 'integrity["ok"] is True',
    "canonical.phase == \"referral_received\"", "MedicationOrder", "EpisodeTransitionV9",
):
    assert proof in smoke_text, f"v24 connected proof missing: {proof}"
assert "runpy.run_path" in runner_text

for token in (
    "Hospital pilot authority", "STOP PILOT", "Rollback", "Current blockers",
    "Critical hospital journeys", "SHADOW COMPARISON", "IMMUTABLE CONTROL HISTORY", "Clinical boundary",
):
    assert token in ui_text, f"v24 UI missing: {token}"
assert '"/pilot-control"' in system_text

print("BOUNDED_PILOT_CONTROL_V24_SAFETY_AUDIT_PASSED")
