from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "apps" / "web" / "lib" / "hospital-modules.ts"
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

    required_shell_bits = [
        "primaryHospitalModules",
        "secondaryHospitalModules",
        "moduleByTitle",
        "getSession",
        "clearSession",
        "contentFor(title, children, user)",
    ]
    for bit in required_shell_bits:
        if bit not in shell:
            fail(f"hospital-shell missing: {bit}")

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
