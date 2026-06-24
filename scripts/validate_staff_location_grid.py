from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

checks = {
    "hospital board route": ROOT / "apps/web/app/hospital-board/page.tsx",
    "staff location grid": ROOT / "apps/web/components/staff-location-grid.tsx",
    "clinical catalogue": ROOT / "apps/web/lib/clinical-catalogue.ts",
}

for label, path in checks.items():
    if not path.exists():
        raise SystemExit(f"Missing {label}: {path}")

route = checks["hospital board route"].read_text()
grid = checks["staff location grid"].read_text()
catalogue = checks["clinical catalogue"].read_text()

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
    "procedureForWork",
    "pharmacyLabels",
    "missing owner/location/next",
    "procedure-generated medication dependencies",
]

for token in required_grid:
    if token not in grid:
        raise SystemExit(f"Staff location grid missing required usability/logic token: {token}")

required_catalogue = [
    "procedureCatalogue",
    "pharmacyCatalogue",
    "MRI",
    "CT",
    "Major theatre",
    "Recovery monitoring",
    "Discharge",
    "anaesthetic-induction",
    "contrast-agent",
]

for token in required_catalogue:
    if token not in catalogue:
        raise SystemExit(f"Clinical catalogue missing required procedure/pharmacy token: {token}")

print("STAFF LOCATION GRID VALIDATION PASSED")
