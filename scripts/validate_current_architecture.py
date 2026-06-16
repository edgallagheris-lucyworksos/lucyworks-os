from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    ROOT / "apps/web/lib/hospital-modules.ts",
    ROOT / "apps/web/components/hospital-shell.tsx",
    ROOT / "apps/web/components/bvs-flow-action-board.tsx",
    ROOT / "apps/web/components/lucy-intake-board.tsx",
    ROOT / "apps/web/app/flow/page.tsx",
    ROOT / "apps/web/app/lucy-intake/page.tsx",
]

ROUTES = [
    "/hospital-board",
    "/lucy-intake",
    "/flow",
    "/resources",
    "/my-shift",
    "/lucy-clinical",
    "/bvs-public-map",
]

MARKERS = [
    "BvsFlowActionBoard",
    "LucyIntakeBoard",
    "bvsFlowStages",
    "hospitalModules",
    "primaryHospitalModules",
    "secondaryHospitalModules",
]


def fail(message: str):
    print(f"CURRENT ARCHITECTURE CHECK FAILED: {message}")
    sys.exit(1)


content = ""
for path in REQUIRED:
    if not path.exists():
        fail(f"missing {path.relative_to(ROOT)}")
    content += path.read_text(encoding="utf-8") + "\n"

modules = (ROOT / "apps/web/lib/hospital-modules.ts").read_text(encoding="utf-8")
for route in ROUTES:
    if route not in modules:
        fail(f"route missing {route}")

for marker in MARKERS:
    if marker not in content:
        fail(f"marker missing {marker}")

print("CURRENT ARCHITECTURE CHECK PASSED")
