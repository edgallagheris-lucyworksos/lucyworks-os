from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTE = ROOT / "apps/api/app/operational_automation_v20_routes.py"
MODEL = ROOT / "apps/api/app/operational_automation_v20_models.py"
MAIN = ROOT / "apps/api/app/main.py"
MIGRATION = ROOT / "apps/api/migrations/versions/0015_operational_automation_v20.py"
RESTORE = ROOT / "scripts/restore-rehearsal.sh"
SMOKE = ROOT / "apps/api/operational_automation_v20_smoke_test.py"

for path in (ROUTE, MODEL, MAIN, MIGRATION, RESTORE, SMOKE):
    assert path.exists(), f"missing v20 file: {path}"

route_text = ROUTE.read_text()
main_text = MAIN.read_text()
migration_text = MIGRATION.read_text()
restore_text = RESTORE.read_text()
smoke_text = SMOKE.read_text()

required_route_tokens = (
    'prefix="/api/v20/automation"',
    "AutomationDecisionV20",
    "WorkItem",
    "commitActions",
    "action_fingerprint",
    "humanAuthorityRequired",
    "ensure_commit_authority",
    "create_evidence_event",
    "automatic_rescheduling",
    "clinical_phase_transition",
)
for token in required_route_tokens:
    assert token in route_text, f"v20 route missing control: {token}"

for forbidden in (
    "MedicationOrder(",
    "MedicationAdministration(",
    "EpisodeTransitionV9(",
    "EpisodeClosureV9(",
    ".phase =",
    '.status = "discharged"',
    ".status = 'discharged'",
):
    assert forbidden not in route_text, f"v20 automation must not perform forbidden action: {forbidden}"

tree = ast.parse(route_text)
constructed = {
    node.func.id
    for node in ast.walk(tree)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
}
assert "WorkItem" in constructed, "v20 must retain accountable WorkItem construction for recorded-state delegates"
assert "AutomationDecisionV20" in constructed, "v20 must persist automation decisions"
assert not (constructed & {
    "MedicationOrder",
    "MedicationAdministration",
    "EpisodeTransitionV9",
    "EpisodeClosureV9",
    "ClinicalNoteV8",
}), f"forbidden clinical entity construction: {constructed}"

assert "operational_automation_v20_router" in main_text
assert "app.include_router(operational_automation_v20_router)" in main_text
assert "app.include_router(recorded_state_automation_guard_v21_router)" in main_text
assert "app.include_router(event_driven_automation_guard_v22_router)" in main_text
assert main_text.index("app.include_router(event_driven_automation_guard_v22_router)") < main_text.index(
    "app.include_router(recorded_state_automation_guard_v21_router)"
), "v22 recorded-delay guard must resolve before the v21 and generic v20 evaluators"
assert main_text.index("app.include_router(recorded_state_automation_guard_v21_router)") < main_text.index(
    "app.include_router(operational_automation_v20_router)"
), "v21 recorded-source guard must resolve before the generic v20 evaluator"
assert 'revision: str = "0015_operational_automation_v20"' in migration_text
assert 'down_revision: Union[str, None] = "0014_speech_capture_v19"' in migration_text
assert "0017_automation_operator_control_v23" in restore_text
assert "automationdecisionv20" in restore_text

for proof in (
    "anonymous.status_code == 401",
    "forbidden.status_code == 409",
    'forbidden.json()["detail"]["code"] == "recorded_source_required"',
    "critical_forbidden.status_code == 409",
    "gaps_forbidden.status_code == 409",
    "delay_forbidden.status_code == 409",
    'delay_forbidden.json()["detail"]["code"] == "recorded_source_required"',
    'delay_preview["decision"]["outcome"] == "previewed"',
    "work == []",
    "notes == []",
    "medication_orders == []",
    "transitions == []",
):
    assert proof in smoke_text, f"v20 smoke proof missing: {proof}"

print("OPERATIONAL_AUTOMATION_V20_SAFETY_AUDIT_PASSED")
