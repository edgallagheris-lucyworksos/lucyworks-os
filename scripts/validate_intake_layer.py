from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    ROOT / "apps" / "web" / "components" / "lucy-intake-board.tsx",
    ROOT / "apps" / "web" / "app" / "lucy-intake" / "page.tsx",
    ROOT / "apps" / "web" / "lib" / "hospital-modules.ts",
    ROOT / "apps" / "web" / "lib" / "bvs-public-pathways.ts",
]
MARKERS = [
    "LucyIntake",
    "front-door coordinator",
    "Incoming",
    "Triage needed",
    "Owner / consent / estimate",
    "Waiting diagnostics",
    "Waiting clinical owner",
    "Bed / ward / ICU",
    "Ready for procedure",
    "Discharge / collection",
    "urgent-referral",
    "routine-referral",
    "request-advice",
    "owner-consult-journey",
    "insurance-payment",
    "aftercare-discharge",
    "teer-cardiology",
    "lucy-intake",
    "intake",
]


def fail(message: str):
    print(f"INTAKE LAYER CHECK FAILED: {message}")
    sys.exit(1)


content = ""
for path in FILES:
    if not path.exists():
        fail(f"missing {path.relative_to(ROOT)}")
    content += path.read_text(encoding="utf-8")

for marker in MARKERS:
    if marker not in content:
        fail(f"missing marker {marker}")

print("INTAKE LAYER CHECK PASSED")
