from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    ROOT / "apps" / "web" / "lib" / "bvs-public-operating-scale.ts",
    ROOT / "apps" / "web" / "lib" / "bvs-public-pathways.ts",
    ROOT / "apps" / "web" / "lib" / "bvs-public-role-map.ts",
    ROOT / "apps" / "web" / "components" / "bvs-public-site-board.tsx",
    ROOT / "apps" / "web" / "app" / "bvs-public-map" / "page.tsx",
]
MARKERS = [
    "publicMinimumTeamSize: 100",
    "bvsPublicCapacityAreas",
    "bvsPublicPathways",
    "urgent-referral",
    "routine-referral",
    "request-advice",
    "owner-consult-journey",
    "insurance-payment",
    "teer-cardiology",
    "bvsPublicRoleMap",
    "clinical-director",
    "hospital-manager",
    "service-heads",
    "BvsPublicSiteBoard",
]


def fail(message: str):
    print(f"BVS PUBLIC SITE CHECK FAILED: {message}")
    sys.exit(1)


content = ""
for path in FILES:
    if not path.exists():
        fail(f"missing {path.relative_to(ROOT)}")
    content += path.read_text(encoding="utf-8")

for marker in MARKERS:
    if marker not in content:
        fail(f"missing marker {marker}")

print("BVS PUBLIC SITE LAYER CHECK PASSED")
