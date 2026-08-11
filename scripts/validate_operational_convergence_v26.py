from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = {
    "models": ROOT / "apps/api/app/operational_context_v26_models.py",
    "context_service": ROOT / "apps/api/app/operating_context_v26_service.py",
    "command_service": ROOT / "apps/api/app/operational_command_v26_service.py",
    "routes": ROOT / "apps/api/app/operational_context_v26_routes.py",
    "migration": ROOT / "apps/api/migrations/versions/0020_operational_convergence_v26.py",
    "proof": ROOT / "apps/api/operational_convergence_v26_smoke_test.py",
    "page": ROOT / "apps/web/app/operating-context/page.tsx",
    "bar": ROOT / "apps/web/components/operating-context-v26-bar.tsx",
    "docs": ROOT / "docs/OPERATIONAL_CONVERGENCE_V26.md",
}

for label, path in REQUIRED_FILES.items():
    assert path.exists(), f"missing {label}: {path}"

models = REQUIRED_FILES["models"].read_text()
context_service = REQUIRED_FILES["context_service"].read_text()
command_service = REQUIRED_FILES["command_service"].read_text()
routes = REQUIRED_FILES["routes"].read_text()
migration = REQUIRED_FILES["migration"].read_text()
proof = REQUIRED_FILES["proof"].read_text()
page = REQUIRED_FILES["page"].read_text()
bar = REQUIRED_FILES["bar"].read_text()
docs = REQUIRED_FILES["docs"].read_text()
main = (ROOT / "apps/api/app/main.py").read_text()
layout = (ROOT / "apps/web/app/layout.tsx").read_text()
system_control = (ROOT / "apps/web/app/system-control/page.tsx").read_text()

for model in (
    "OrganisationV26", "SiteV26", "SiteMembershipV26", "ActiveOperatingContextV26",
    "ContextSwitchEvidenceV26", "CanonicalCommandV26", "LegacyRouteConvergenceV26", "OperationalImpactV26",
):
    assert f"class {model}" in models, model

assert 'clinical_mutation_performed: bool = False' in models
assert 'DEFAULT_PREMISES_REF = "bvs-bristol"' in context_service
assert 'default_premises_forbidden' in context_service
assert 'cross_site_write_rejected' in context_service
assert 'stale_operating_context' in context_service
assert 'site_not_authorised' in context_service
assert 'operating_context_switched' in context_service
assert 'V26_CONTEXT_BOOTSTRAP_ENABLED' in context_service

for command in (
    "patient_blocker", "handover_request", "critical_result_received", "consent_review_request",
    "estimate_review_request", "discharge_review_request", "safety_escalation", "service_restriction",
    "equipment_downtime", "medication_supply_delay",
):
    assert f'"{command}"' in command_service, command

assert 'clinical_mutation_performed=False' in command_service
assert 'idempotency_key' in command_service
assert 'actorName' in command_service and 'authSource' in command_service
assert 'OperationalImpactV26(' in command_service
assert 'create_action(' in command_service
assert 'existing_safety_ref' in command_service

for route in (
    '@router.get("/api/v26/context")', '@router.post("/api/v26/context/switch")',
    '@router.post("/api/v26/commands")', '@router.get("/api/v26/operational-view")',
    '@router.get("/api/v26/convergence")', '@router.patch("/api/patient-care/episodes/{episode_id}/state")',
    '@router.post("/api/control-plane/handovers")', '@router.post("/api/control-plane/critical-results")',
):
    assert route in routes, route

assert 'class _DeferredCommitSession' in routes
assert 'self._session.flush()' in routes
assert 'app.include_router(operational_context_v26_router)' in main
assert main.index('app.include_router(operational_context_v26_router)') < main.index('app.include_router(safety_bridge_v25_router)')
assert 'revision: str = "0020_operational_convergence_v26"' in migration
assert 'down_revision: Union[str, None] = "0019_cross_system_safety_control_v25"' in migration

for proof_text in (
    "cross-site writes rejected", "Default-premises", "clinicalMutationPerformed", "Spoofed Browser",
    "HANDOVER-V26", "RESULT-V26", "mri-downtime-v26", "verify_event_chain",
):
    assert proof_text.lower() in proof.lower(), proof_text

assert 'OperatingContextV26Bar' in layout
assert '/operating-context' in system_control
assert '/api/v26/context' in bar
assert '/api/v26/operational-view' in bar
assert '/api/v26/commands' in page
assert 'It does not complete consent, discharge, prescribing or treatment.' in page

for principle in (
    "Verified person + authorised role + authorised hospital context", "does not diagnose",
    "commit together or roll back together", "not a live hospital deployment",
):
    assert principle.lower() in docs.lower(), principle

print("V26 operating context, command convergence, atomicity and clinical boundary validated")
