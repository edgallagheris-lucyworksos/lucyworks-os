from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

CANONICAL_DIRS = [
    ROOT / "apps/web",
    ROOT / "apps/api",
]

LEGACY_DIRS = [
    ROOT / "frontend",
    ROOT / "backend",
]

REQUIRED = [
    ROOT / "PRODUCT_CONTRACT.md",
    ROOT / "AGENTS.md",
    ROOT / "apps/web/lib/hospital-modules.ts",
    ROOT / "apps/web/components/hospital-shell.tsx",
    ROOT / "apps/web/components/bvs-flow-action-board.tsx",
    ROOT / "apps/web/components/lucy-intake-board.tsx",
    ROOT / "apps/web/app/flow/page.tsx",
    ROOT / "apps/web/app/lucy-intake/page.tsx",
    ROOT / "apps/api/app/main.py",
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


for path in CANONICAL_DIRS:
    if not path.is_dir():
        fail(f"missing canonical directory {path.relative_to(ROOT)}")

for path in LEGACY_DIRS:
    if path.exists():
        fail(
            f"legacy duplicate implementation still present at {path.relative_to(ROOT)}; "
            "active product code must live under apps/web and apps/api"
        )

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

root_package = (ROOT / "package.json").read_text(encoding="utf-8")
for canonical_path in ("apps/api", "apps/web"):
    if canonical_path not in root_package:
        fail(f"root package scripts do not reference canonical path {canonical_path}")

for forbidden in ('cd backend', 'cd frontend'):
    if forbidden in root_package:
        fail(f"root package scripts still target legacy path: {forbidden}")

print("CURRENT ARCHITECTURE CHECK PASSED")
