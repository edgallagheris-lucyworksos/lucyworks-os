from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    ROOT / "apps" / "web" / "lib" / "canonical-operational-work.ts",
    ROOT / "apps" / "web" / "components" / "hospital-operating-console.tsx",
    ROOT / "apps" / "web" / "components" / "work-area-board.tsx",
    ROOT / "apps" / "web" / "app" / "theatre" / "page.tsx",
    ROOT / "apps" / "web" / "app" / "imaging" / "page.tsx",
    ROOT / "apps" / "web" / "app" / "icu-wards" / "page.tsx",
    ROOT / "apps" / "web" / "app" / "lucy-pharm" / "page.tsx",
]
REQUIRED = [
    "canonicalOperationalWork",
    "workItemsForArea",
    "highPressureWorkItems",
    "WorkAreaBoard",
    "QueueDetailDrawer",
    "OperationalTarget",
    "setSelected",
    "open drawer",
    "owner",
    "blocker",
    "next",
    "due",
    "Theatre",
    "Imaging",
    "Care Area",
    "Supply",
    "/hospital-board",
    "/rota",
    "/flow",
]


def fail(message: str):
    print(f"WORK AREA BOARD CHECK FAILED: {message}")
    sys.exit(1)


content = ""
for path in FILES:
    if not path.exists():
        fail(f"missing {path.relative_to(ROOT)}")
    text = path.read_text(encoding="utf-8")
    if path.name == "page.tsx" and "ModulePage" in text:
        fail(f"generic ModulePage remains in {path.relative_to(ROOT)}")
    content += text + "\n"

for marker in REQUIRED:
    if marker not in content:
        fail(f"missing marker {marker}")

print("WORK AREA BOARD CHECK PASSED")
