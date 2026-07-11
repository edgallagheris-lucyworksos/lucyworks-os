from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

checks = {
    "hospital board route": ROOT / "apps/web/app/hospital-board/page.tsx",
    "staff location grid": ROOT / "apps/web/components/staff-location-grid.tsx",
    "quick assignment strip": ROOT / "apps/web/components/quick-assignment-strip.tsx",
    "governance gates panel": ROOT / "apps/web/components/governance-gates-panel.tsx",
    "referral pathway panel": ROOT / "apps/web/components/referral-pathway-generator.tsx",
    "day control store": ROOT / "apps/web/lib/day-control-store.ts",
    "api main": ROOT / "apps/api/app/main.py",
    "safe assignment route": ROOT / "apps/api/app/day_control_assignment_routes.py",
    "governance route": ROOT / "apps/api/app/day_control_governance_routes.py",
    "clinical catalogue": ROOT / "apps/web/lib/clinical-catalogue.ts",
    "conflict route": ROOT / "apps/api/app/day_control_conflict_routes.py",
    "referral pathway generator": ROOT / "apps/web/lib/referral-pathway.ts",
}

for label, path in checks.items():
    if not path.exists():
        raise SystemExit(f"Missing {label}: {path}")

route = checks["hospital board route"].read_text()
grid = checks["staff location grid"].read_text()
quick_assign = checks["quick assignment strip"].read_text()
governance_panel = checks["governance gates panel"].read_text()
panel = checks["referral pathway panel"].read_text()
store = checks["day control store"].read_text()
api_main = checks["api main"].read_text()
safe_assignment_route = checks["safe assignment route"].read_text()
governance_route = checks["governance route"].read_text()
catalogue = checks["clinical catalogue"].read_text()
conflict_route = checks["conflict route"].read_text()
pathway = checks["referral pathway generator"].read_text()

required_route = [
    "StaffLocationGrid",
    "@/components/staff-location-grid",
]

for token in required_route:
    if token not in route:
        raise SystemExit(f"Hospital board route is not wired to StaffLocationGrid: missing {token}")

for forbidden in ["NowBoard", "DayControlGrid", "AccountabilityGrid"]:
    if forbidden in route:
        raise SystemExit(f"Hospital board route still references fallback/old board: {forbidden}")

required_grid = [
    "Vet / clinician",
    "Imaging",
    "Anaesthesia",
    "Nurse",
    "PCA / support",
    "Reception / admin",
    "Pharmacy / stock",
    "Coordinator",
    "Blocked",
    "MRI",
    "Theatre",
    "Ward",
    "ReferralPathwayGenerator",
    "QuickAssignmentStrip",
    "GovernanceGatesPanel",
    "blocks={blocks}",
    "onGenerate={addBlocks}",
    "syncStatus={syncStatus}",
    "assignBlock",
    "clearAssignment",
    "onAssign={assignBlock}",
    "onClear={clearAssignment}",
    "type BoardMode = \"role\" | \"person\"",
    "People columns",
    "Role columns",
    "personColumnKey",
    "personViewColumns",
    "Unassigned",
    "assignedStaffName",
    "procedureForWork",
    "protectedTimeLabel",
    "pharmacyLabels",
    "Governance gates stop unsafe referral flow",
]

for token in required_grid:
    if token not in grid:
        raise SystemExit(f"Staff location grid missing required usability/logic token: {token}")

required_quick_assign = [
    "QuickAssignmentStrip",
    "staff-options",
    "resource-options",
    "procedureForWork",
    "type ProtectedWindow",
    "type Candidate",
    "protectedWindow",
    "overlaps",
    "sameCase",
    "conflictFor",
    "staffScore",
    "resourceScore",
    "staffCandidates",
    "resourceCandidates",
    "recommended:",
    "busy until",
    "Assign with warning",
    "Quick staff",
    "Resource",
    "Assign",
    "Clear",
    "onAssign(block.id",
    "onClear(block.id)",
    "recommended by role, area and protected time",
]

for token in required_quick_assign:
    if token not in quick_assign:
        raise SystemExit(f"Quick assignment strip missing smart assignment token: {token}")

required_governance_panel = [
    "GovernanceGatesPanel",
    "/api/day-control/governance-gates",
    "Clinical/admin gates",
    "Consent, estimate, insurance, pharmacy, owner update and referring-vet report governance",
    "hard blocks",
    "warnings",
]

for token in required_governance_panel:
    if token not in governance_panel:
        raise SystemExit(f"Governance panel missing required UI token: {token}")

required_panel = [
    "Generate referral pathway",
    "onGenerate",
    "generateReferralPathway",
    "Referral consult",
    "MRI pathway",
    "CT pathway",
    "Major surgery pathway",
    "Discharge pathway",
]

for token in required_panel:
    if token not in panel:
        raise SystemExit(f"Referral pathway panel missing required UI token: {token}")

if "useDayControlStore" in panel:
    raise SystemExit("Referral pathway panel must use board-provided store actions, not its own store instance")

required_store = [
    "function addBlocks",
    "function assignBlock",
    "function clearAssignment",
    "apiReplaceBlocks(nextBlocks)",
    "apiSafeAssign",
    "/safe-assign",
    "allowWarning: true",
    "assignment checking",
    "safe assignment request failed",
    "return { blocks, pressure, blocked, addBlocks",
]

for token in required_store:
    if token not in store:
        raise SystemExit(f"Day-control store missing generated-pathway, assignment or safe-assign support: {token}")

required_api_main = [
    "day_control_assignment_router",
    "day_control_assignment_routes",
    "app.include_router(day_control_assignment_router)",
    "day_control_governance_router",
    "day_control_governance_routes",
    "app.include_router(day_control_governance_router)",
]

for token in required_api_main:
    if token not in api_main:
        raise SystemExit(f"API main missing day-control router wiring: {token}")

required_safe_assignment_route = [
    "AssignmentRecommendationRequest",
    "SafeAssignPayload",
    "@router.post(\"/assignment-recommendations\")",
    "@router.patch(\"/blocks/{block_id}/safe-assign\")",
    "safe_assign_block",
    "allowWarning",
    "decision",
    "allowed",
    "warn",
    "block",
    "_protected_window",
    "_overlaps",
    "_candidate_staff",
    "_candidate_resources",
    "_assignment_warnings",
    "staff_protected_time_overlap",
    "resource_protected_time_overlap",
    "safe_assign",
]

for token in required_safe_assignment_route:
    if token not in safe_assignment_route:
        raise SystemExit(f"Safe assignment route missing backend safety token: {token}")

required_governance_route = [
    "@router.get(\"/governance-gates\")",
    "list_governance_gates",
    "consent_gate",
    "estimate_gate",
    "insurance_gate",
    "pharmacy_gate",
    "owner_update_gate",
    "referring_vet_report_gate",
    "Procedure blocked: consent not clear",
    "Procedure blocked: estimate not clear",
    "Procedure blocked: pharmacy not ready",
    "Discharge blocked: owner update missing",
    "Case cannot close: referring-vet report missing",
]

for token in required_governance_route:
    if token not in governance_route:
        raise SystemExit(f"Governance route missing hard gate token: {token}")

required_catalogue = [
    "procedureCatalogue",
    "pharmacyCatalogue",
    "MRI referral pathway",
    "CT referral pathway",
    "Major surgery referral pathway",
    "Referral discharge",
    "setupMinutes",
    "handoverMinutes",
    "contingencyMinutes",
    "referralAdminMinutes",
    "protectedMinutesForProcedure",
    "protectedTimeLabel",
    "anaesthetic-induction",
    "contrast-agent",
]

for token in required_catalogue:
    if token not in catalogue:
        raise SystemExit(f"Clinical catalogue missing required referral contingency/procedure token: {token}")

required_conflict_route = [
    "PROCEDURE_PROFILES",
    "_protected_window",
    "_overlaps",
    "staff_protected_time_overlap",
    "resource_protected_time_overlap",
    "protectedStart",
    "protectedEnd",
    "protectedMinutes",
]

for token in required_conflict_route:
    if token not in conflict_route:
        raise SystemExit(f"Conflict route missing protected-time capacity logic: {token}")

required_pathway = [
    "generateReferralPathway",
    "Referral triage",
    "Consent and estimate gate",
    "Pharmacy preparation",
    "Clinical handover",
    "Owner update",
    "Report to referring vet",
    "episodeRef",
    "generatedFrom: \"referral-pathway\"",
]

for token in required_pathway:
    if token not in pathway:
        raise SystemExit(f"Referral pathway generator missing required workflow token: {token}")

print("STAFF LOCATION GRID VALIDATION PASSED")
