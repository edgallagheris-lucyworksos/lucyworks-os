from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "apps/api/app/event_driven_automation_v22_models.py"
SERVICE = ROOT / "apps/api/app/event_driven_automation_v22_service.py"
ROUTES = ROOT / "apps/api/app/event_driven_automation_v22_routes.py"
RUNTIME = ROOT / "apps/api/app/event_driven_automation_v22_runtime.py"
CONCURRENCY = ROOT / "apps/api/app/event_driven_automation_v22_concurrency_patch.py"
MAIN = ROOT / "apps/api/app/main.py"
MIGRATION = ROOT / "apps/api/migrations/versions/0016_event_driven_automation_v22.py"
CURRENT_MIGRATION = ROOT / "apps/api/migrations/versions/0017_automation_operator_control_v23.py"
SMOKE = ROOT / "apps/api/event_driven_automation_v22_smoke_test.py"

for path in (MODELS, SERVICE, ROUTES, RUNTIME, CONCURRENCY, MAIN, MIGRATION, CURRENT_MIGRATION, SMOKE):
    assert path.exists(), f"missing v22 artifact: {path}"

models_text = MODELS.read_text()
service_text = SERVICE.read_text()
routes_text = ROUTES.read_text()
runtime_text = RUNTIME.read_text()
concurrency_text = CONCURRENCY.read_text()
main_text = MAIN.read_text()
migration_text = MIGRATION.read_text()
current_migration_text = CURRENT_MIGRATION.read_text()
smoke_text = SMOKE.read_text()

for token in (
    "AutomationRuntimeConfigV22",
    "AutomationTriggerV22",
    "uq_automationtriggerv22_source_state_mode",
    'mode: str = Field(default="disabled"',
    "source_state_hash",
    "error_detail",
):
    assert token in models_text, f"v22 model control missing: {token}"

for token in (
    "evaluate_recorded_operational_delay",
    "derive_delay",
    "recorded_source_required",
    "governed_commit",
    "preview_only",
    "dispatch_source",
    "scan_and_dispatch",
    "dry_run_episode",
    "system_automation",
    "source_version",
    "source_state_hash",
):
    assert token in service_text + routes_text, f"v22 authority control missing: {token}"

for token in (
    'event.listen(SQLAlchemySession, "after_flush"',
    'event.listen(SQLAlchemySession, "after_commit"',
    "dispatch_source(source_type, source_ref)",
    "source transaction has already committed",
    "background_scan_enabled",
):
    assert token in runtime_text, f"v22 runtime control missing: {token}"

assert "if created and row.status == \"queued\"" in concurrency_text
assert "Only that creator may automatically execute" in concurrency_text
assert "event_driven_automation_v22_concurrency_patch" in main_text
assert main_text.index("event_driven_automation_guard_v22_router") < main_text.index("recorded_state_automation_guard_v21_router")
assert "install_event_driven_automation_v22(app)" in main_text

for forbidden in (
    "MedicationOrder(",
    "MedicationAdministration(",
    "EpisodeTransitionV9(",
    "EpisodeClosureV9(",
    "ClinicalNoteV8(",
    '.status = "acknowledged"',
    ".phase =",
    '.status = "discharged"',
    ".status = 'discharged'",
):
    assert forbidden not in service_text + routes_text + runtime_text, f"v22 performs forbidden action: {forbidden}"

constructed: set[str] = set()
for text in (service_text, routes_text, runtime_text):
    tree = ast.parse(text)
    constructed |= {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
assert not (constructed & {
    "MedicationOrder",
    "MedicationAdministration",
    "EpisodeTransitionV9",
    "EpisodeClosureV9",
    "ClinicalNoteV8",
}), f"v22 constructed forbidden clinical entities: {constructed}"

assert 'revision: str = "0016_event_driven_automation_v22"' in migration_text
assert 'down_revision: Union[str, None] = "0015_operational_automation_v20"' in migration_text
assert "AutomationRuntimeConfigV22.__table__.create" in migration_text
assert "AutomationTriggerV22.__table__.create" in migration_text
assert 'down_revision: Union[str, None] = "0016_event_driven_automation_v22"' in current_migration_text

for proof in (
    'mode="disabled"',
    'mode="preview_only"',
    'mode="governed_commit"',
    "ThreadPoolExecutor",
    'generic_delay.status_code == 409',
    'failed_trigger.status == "failed"',
    'source observation was rolled back',
    'integrity["ok"] is True',
):
    assert proof in smoke_text, f"v22 connected proof missing: {proof}"

print("EVENT_DRIVEN_AUTOMATION_V22_SAFETY_AUDIT_PASSED")
