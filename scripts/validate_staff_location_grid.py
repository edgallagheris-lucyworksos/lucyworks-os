from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

checks = {
    "hospital board route": ROOT / "apps/web/app/hospital-board/page.tsx",
    "staff location grid": ROOT / "apps/web/components/staff-location-grid.tsx",
    "referral pathway panel": ROOT / "apps/web/components/referral-pathway-generator.tsx",
    "day control store": ROOT / "apps/web/lib/day-control-store.ts",
    "clinical catalogue": ROOT / "apps/web/lib/clinical-catalogue.ts",
    "conflict route": ROOT / "apps/api/app/day_control_conflict_routes.py",
    "referral pathway generator": ROOT / "apps/web/lib/referral-pathway.ts",
}

for label, path in checks.items():
    if not path.exists():
        raise SystemExit(f"Missing {label}: {path}")

route = checks["hospital board route"].read_text()
grid = checks["staff location grid"].read_text()
panel = checks["referral pathway panel"].read_text()
store = checks["day control store"].read_text()
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
    "onGenerate={addBlocks}",
    "syncStatus={syncStatus}",
    "procedureForWork",
    "protectedTimeLabel",
    "pharmacyLabels",
    "missing owner/location/next",
    "procedure-generated medication dependencies",
]

for token in required_grid:
    if token not in grid:
        raise SystemExit(f"Staff location grid missing required usability/logic token: {token}")

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
    "apiReplaceBlocks(nextBlocks)",
    "return { blocks, pressure, blocked, addBlocks",
]

for token in required_store:
    if token not in store:
        raise SystemExit(f"Day-control store missing generated-pathway append support: {token}")

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
