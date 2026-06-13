from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "apps" / "web" / "lib" / "hospital-modules.ts"
OPERATING_MODEL = ROOT / "apps" / "web" / "lib" / "hospital-operating-model.ts"
PUBLIC_PROFILE = ROOT / "apps" / "web" / "lib" / "bvs-public-facility-profile.ts"
SERVICE_WORKFLOWS = ROOT / "apps" / "web" / "lib" / "bvs-service-workflows.ts"
FLOW_MAP = ROOT / "apps" / "web" / "lib" / "bvs-flow-map.ts"
CLINICAL_BOARD = ROOT / "apps" / "web" / "components" / "bvs-clinical-service-board.tsx"
FLOW_BOARD = ROOT / "apps" / "web" / "components" / "bvs-flow-board.tsx"
SHELL = ROOT / "apps" / "web" / "components" / "hospital-shell.tsx"
WORKFLOW = ROOT / ".github" / "workflows" / "lucyworks-check.yml"
CHECK_SCRIPT = ROOT / "scripts" / "check-monorepo.sh"

EXPECTED = {
    "now": "/hospital-board",
    "flow": "/flow",
    "ops": "/resources",
    "hr": "/my-shift",
    "pulse": "/interrupts",
    "clinical": "/lucy-clinical",
    "care": "/nurse-dashboard",
    "move": "/pca-dashboard",
    "gov": "/lucy-gov",
    "pharm": "/lucy-pharm",
    "system": "/system-control",
}

REQUIRED_BACKEND_ENDPOINTS = [
    "/api/product/now",
    "/api/product/flow",
    "/api/product/resources",
    "/api/role-queues/my-shift",
    "/api/conflict-engine/pulse",
    "/api/role-queues/nurse",
    "/api/role-queues/pca",
    "/api/audit",
    "/api/health",
]

REQUIRED_OPERATING_UNITS = [
    "publicVerifiedTheatreUnits",
    "publicVerifiedInterventionalUnits",
    "internalConfiguredTheatreLikeSpaceCount = 11",
    "theatreLikeUnits",
    "MRI",
    "CT",
    "X-ray / radiography",
    "Ultrasound",
    "Radiotherapy / linear accelerator",
    "Urgent laboratory",
    "Pharmacy",
    "Insurance / pre-authorisation",
    "ICU / critical care",
    "Recovery",
    "Canine / feline wards",
    "Triage / reception intake",
    "Owner communications",
    "Stock / equipment readiness",
    "Governance / audit",
]

REQUIRED_PUBLIC_PROFILE = [
    "publicVerifiedOperatingTheatres: 5",
    "publicVerifiedInterventionalSuites: 1",
    "theatreLikeSpacesConfigurable: true",
    "1.5 Tesla Siemens Sempra MRI",
    "64 slice Siemens go.TOP CT scanner",
    "linear accelerator radiotherapy",
]

REQUIRED_SERVICE_WORKFLOWS = [
    "diagnostic-imaging",
    "emergency-critical-care",
    "oncology-radiotherapy",
    "interventional-radiology",
    "soft-tissue-surgery",
    "orthopaedics",
    "neurology-neurosurgery",
    "internal-medicine",
    "cardiology",
    "ophthalmology",
    "dermatology",
    "dentistry-maxillofacial",
    "anaesthesia-analgesia",
]

REQUIRED_FLOW_STAGES = [
    "arrival-triage",
    "ecc-stabilisation",
    "diagnostic-imaging",
    "service-ownership",
    "procedure-theatre",
    "interventional-suite",
    "recovery-icu-ward",
    "owner-update",
    "pharmacy-discharge",
]


def fail(message: str) -> None:
    print(f"ARCHITECTURE CHECK FAILED: {message}")
    sys.exit(1)


def require_file(path: Path) -> str:
    if not path.exists():
        fail(f"missing file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def route_to_dir(route: str) -> Path:
    route_part = route.strip("/") or "hospital-board"
    return ROOT / "apps" / "web" / "app" / route_part / "page.tsx"


def main() -> None:
    modules = require_file(MODULES)
    operating_model = require_file(OPERATING_MODEL)
    public_profile = require_file(PUBLIC_PROFILE)
    service_workflows = require_file(SERVICE_WORKFLOWS)
    flow_map = require_file(FLOW_MAP)
    clinical_board = require_file(CLINICAL_BOARD)
    flow_board = require_file(FLOW_BOARD)
    shell = require_file(SHELL)
    workflow = require_file(WORKFLOW)
    check_script = require_file(CHECK_SCRIPT)

    for module_id, route in EXPECTED.items():
        if f'id: "{module_id}"' not in modules:
            fail(f"module id missing from hospital-modules.ts: {module_id}")
        if f'route: "{route}"' not in modules:
            fail(f"route missing for {module_id}: {route}")
        page = route_to_dir(route)
        if not page.exists():
            fail(f"route page missing for {module_id}: {page.relative_to(ROOT)}")

    for endpoint in REQUIRED_BACKEND_ENDPOINTS:
        if endpoint not in modules:
            fail(f"endpoint missing from module map: {endpoint}")

    for marker in REQUIRED_OPERATING_UNITS:
        if marker not in operating_model:
            fail(f"operating model missing: {marker}")

    for marker in REQUIRED_PUBLIC_PROFILE:
        if marker not in public_profile:
            fail(f"public BVS profile missing: {marker}")

    for marker in REQUIRED_SERVICE_WORKFLOWS:
        if marker not in service_workflows:
            fail(f"BVS service workflow missing: {marker}")

    for marker in REQUIRED_FLOW_STAGES:
        if marker not in flow_map:
            fail(f"BVS flow stage missing: {marker}")

    required_shell_bits = [
        "primaryHospitalModules",
        "secondaryHospitalModules",
        "moduleByTitle",
        "getSession",
        "clearSession",
        "contentFor(title, children, user)",
        "BvsClinicalServiceBoard",
        "BvsFlowBoard",
    ]
    for bit in required_shell_bits:
        if bit not in shell:
            fail(f"hospital-shell missing: {bit}")

    if "bvsServiceWorkflows" not in clinical_board:
        fail("clinical board is not wired to BVS service workflows")
    if "bvsFlowStages" not in flow_board:
        fail("flow board is not wired to BVS flow stages")

    banned_hardcoded = ["/lucy-flow", "/lucy-ops", "/lucy-hr", "/lucy-pulse"]
    for route in banned_hardcoded:
        if route in shell:
            fail(f"stale hard-coded route remains in shell: {route}")

    if "workflow_dispatch" not in workflow:
        fail("workflow missing manual dispatch trigger")
    if "bash scripts/check-monorepo.sh" not in workflow:
        fail("workflow does not run monorepo check")
    if "validate_lucyworks_architecture.py" not in check_script:
        fail("check-monorepo.sh does not run architecture validator")

    count = len(re.findall(r'id: "', modules))
    if count < len(EXPECTED):
        fail(f"module count too low: {count}")

    print("LUCYWORKS ARCHITECTURE CHECK PASSED")


if __name__ == "__main__":
    main()
