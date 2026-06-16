from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    ROOT / "apps" / "web" / "components" / "hospital-operating-console.tsx",
    ROOT / "apps" / "web" / "app" / "hospital-board" / "page.tsx",
]
MARKERS = [
    "HospitalOperatingConsole",
    "Hospital operating console",
    "Operating lanes",
    "Day sheet",
    "owner + blocker + next action",
    "Route → assign → start → block/complete",
    "Front door",
    "Theatre",
    "Imaging",
    "Ward",
    "ICU / ECC",
    "Pharmacy",
    "People / rota",
    "/lucy-intake",
    "/rota",
    "/flow",
    "/my-shift",
    "/resources",
]


def fail(message: str):
    print(f"OPERATING CONSOLE CHECK FAILED: {message}")
    sys.exit(1)


content = ""
for path in FILES:
    if not path.exists():
        fail(f"missing {path.relative_to(ROOT)}")
    content += path.read_text(encoding="utf-8")

for marker in MARKERS:
    if marker not in content:
        fail(f"missing marker {marker}")

print("OPERATING CONSOLE CHECK PASSED")
