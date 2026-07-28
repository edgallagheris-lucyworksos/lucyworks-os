from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ROOT / "apps/api/app/recorded_state_automation_v21_routes.py"
MAIN = ROOT / "apps/api/app/main.py"
SMOKE = ROOT / "apps/api/recorded_state_automation_v21_smoke_test.py"

for path in (ROUTES, MAIN, SMOKE):
    assert path.exists(), f"missing v21 file: {path}"

routes_text = ROUTES.read_text()
main_text = MAIN.read_text()
smoke_text = SMOKE.read_text()

required = (
    "DATABASE_BACKED_TRIGGER_TYPES",
    "recorded_source_required",
    'ConfigDict(extra="forbid")',
    "ClinicalObservation",
    "CriticalResultAcknowledgement",
    "CanonicalEpisodeState",
    "expectedVersion",
    "expectedStateHash",
    "source_version_conflict",
    "source_state_conflict",
    "factsAcceptedFromBrowser",
    "derivedFromCanonicalDatabase",
    "sourceStateHash",
    "sourceVersion",
)
for token in required:
    assert token in routes_text, f"v21 missing source-authority control: {token}"

assert main_text.index("app.include_router(recorded_state_automation_guard_v21_router)") < main_text.index(
    "app.include_router(operational_automation_v20_router)"
), "v21 generic commit guard must resolve before the v20 generic evaluator"
assert "app.include_router(recorded_state_automation_v21_router)" in main_text

for forbidden in (
    ".concern_level =",
    ".status = \"acknowledged\"",
    ".acknowledged_at =",
    ".gates_json =",
    ".phase =",
    "MedicationOrder(",
    "EpisodeTransitionV9(",
):
    assert forbidden not in routes_text, f"recorded-state adapter must not mutate clinical source state: {forbidden}"

tree = ast.parse(routes_text)
constructed = {
    node.func.id
    for node in ast.walk(tree)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
}
assert "AutomationEvaluate" in constructed
assert not (constructed & {
    "ClinicalObservation",
    "CriticalResultAcknowledgement",
    "CanonicalEpisodeState",
    "MedicationOrder",
    "EpisodeTransitionV9",
}), f"v21 must read, not construct, clinical source records: {constructed}"

for proof in (
    "generic_commit.status_code == 409",
    "override_attempt.status_code == 422",
    "stale_observation.status_code == 409",
    "stale_result.status_code == 409",
    'observation_replay["replayProtected"] is True',
    "result.status == \"awaiting_acknowledgement\"",
    "notes == []",
    "medication_orders == []",
    "transitions == []",
):
    assert proof in smoke_text, f"v21 smoke proof missing: {proof}"

print("RECORDED_STATE_AUTOMATION_V21_AUTHORITY_AUDIT_PASSED")
