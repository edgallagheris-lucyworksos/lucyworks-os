from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    ROOT / "apps" / "web" / "components" / "rota-command-grid.tsx",
    ROOT / "apps" / "web" / "app" / "rota" / "page.tsx",
]
MARKERS = [
    "RotaCommandGrid",
    "Hospital rota grid",
    "Theatre",
    "Imaging",
    "Ward",
    "ICU/ECC",
    "Front door",
    "Pharmacy",
    "Risk",
    "/lucy-intake",
    "/flow",
    "/my-shift",
    "/resources",
]


def fail(message: str):
    print(f"ROTA GRID CHECK FAILED: {message}")
    sys.exit(1)


content = ""
for path in FILES:
    if not path.exists():
        fail(f"missing {path.relative_to(ROOT)}")
    content += path.read_text(encoding="utf-8")

for marker in MARKERS:
    if marker not in content:
        fail(f"missing marker {marker}")

print("ROTA GRID CHECK PASSED")
