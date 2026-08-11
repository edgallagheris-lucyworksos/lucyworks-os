from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTE = ROOT / "apps/api/app/automation_operator_control_v23_routes.py"
MODEL = ROOT / "apps/api/app/automation_operator_control_v23_models.py"
MIGRATION = ROOT / "apps/api/migrations/versions/0017_automation_operator_control_v23.py"
MAIN = ROOT / "apps/api/app/main.py"
SMOKE = ROOT / "apps/api/automation_operator_control_v23_smoke_test.py"
PAGE = ROOT / "apps/web/app/automation-control/page.tsx"
CONTROL = ROOT / "apps/web/components/automation-operator-control-v23.tsx"
WORKSPACE = ROOT / "apps/web/components/operational-workspace-v16.tsx"
BOARD = ROOT / "apps/web/components/automation-board-dock-v23.tsx"
RESPONSIVE = ROOT / "apps/web/components/responsive-hospital-board-v15.tsx"
SYSTEM_CONTROL = ROOT / "apps/web/app/system-control/page.tsx"

for path in (ROUTE, MODEL, MIGRATION, MAIN, SMOKE, PAGE, CONTROL, WORKSPACE, BOARD, RESPONSIVE, SYSTEM_CONTROL):
    assert path.exists(), f"missing v23 file: {path}"

route_text = ROUTE.read_text()
model_text = MODEL.read_text()
migration_text = MIGRATION.read_text()
main_text = MAIN.read_text()
smoke_text = SMOKE.read_text()
control_text = CONTROL.read_text()
workspace_text = WORKSPACE.read_text()
board_text = BOARD.read_text()
responsive_text = RESPONSIVE.read_text()
system_text = SYSTEM_CONTROL.read_text()

for token in (
    'prefix="/api/v23/automation"',
    "GOVERNED_ACKNOWLEDGEMENT",
    "AUTHORISE GOVERNED AUTOMATION",
    "validate_service_configuration",
    "expectedVersion",
    "record_operator_action",
    "dry_run_episode",
    "scan_and_dispatch",
    "process_trigger",
    "sourceStateHash",
    "workItems",
    "AutomationOperatorActionV23",
):
    assert token in route_text, f"v23 route missing control: {token}"

for forbidden in (
    "MedicationOrder(",
    "MedicationAdministration(",
    "EpisodeTransitionV9(",
    "EpisodeClosureV9(",
    ".phase =",
    '.status = "discharged"',
    ".status = 'discharged'",
    "apply_propagated_delay(",
):
    assert forbidden not in route_text, f"operator control must not perform forbidden clinical or scheduling action: {forbidden}"

tree = ast.parse(route_text)
constructed = {
    node.func.id
    for node in ast.walk(tree)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
}
assert "AutomationOperatorActionV23" in constructed
assert not (constructed & {
    "MedicationOrder",
    "MedicationAdministration",
    "EpisodeTransitionV9",
    "EpisodeClosureV9",
    "ClinicalNoteV8",
    "OperationalBlock",
}), f"forbidden entity construction: {constructed}"

assert 'revision: str = "0017_automation_operator_control_v23"' in migration_text
assert 'down_revision: Union[str, None] = "0016_event_driven_automation_v22"' in migration_text
assert "AutomationOperatorActionV23" in model_text
assert "automation_operator_control_v23_router" in main_text
assert "app.include_router(automation_operator_control_v23_router)" in main_text

for token in (
    "Automation authority",
    "Disabled",
    "Preview only",
    "Governed commit",
    "Typed acknowledgement",
    "Validate configuration",
    "Run episode dry run",
    "Reconcile recorded sources",
    "Visible recovery queue",
    "Source → decision → accountable work",
    "No browser-supplied clinical facts",
):
    assert token in control_text, f"operator UI missing usability control: {token}"

assert 'href="/automation-control"' in system_text
assert "Automation evidence" in workspace_text
assert "Clinical responsibility remains with the named team" in workspace_text
assert "AUTOMATION EVIDENCE ON THE MASTER BOARD" in board_text
assert "LucyWorks has not rescheduled care or made a clinical decision" in board_text
assert "AutomationBoardDockV23" in responsive_text

for proof in (
    'initial["configuration"]["mode"] == "disabled"',
    'invalid["valid"] is False',
    'missing_ack.status_code == 409',
    '"AUTHORISE GOVERNED AUTOMATION"',
    'dry_run["workCreated"] is False',
    'red_trigger["status"] == "completed"',
    'retried["trigger"]["status"] == "previewed"',
    'reconciled["count"] >= 2',
    'integrity["ok"] is True',
):
    assert proof in smoke_text, f"v23 proof missing: {proof}"

print("AUTOMATION_OPERATOR_CONTROL_V23_SAFETY_AUDIT_PASSED")
