from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    ROOT / "apps" / "api" / "app" / "staff_assignment.py",
    ROOT / "apps" / "api" / "app" / "queue_routes.py",
    ROOT / "apps" / "api" / "queue_smoke_test.py",
]
MARKERS = [
    "ROLE_TO_STAFF_ROLES",
    "QUEUE_TO_STAFF_ROLES",
    "acceptable_staff_roles",
    "clinical_director_or_ops_manager",
    "bed_capacity_queue",
    "imaging_queue",
    "theatre_queue",
    "pick_staff",
    "owner_user_id",
]


def fail(message: str):
    print(f"STAFF ASSIGNMENT CHECK FAILED: {message}")
    sys.exit(1)


content = ""
for path in FILES:
    if not path.exists():
        fail(f"missing {path.relative_to(ROOT)}")
    content += path.read_text(encoding="utf-8")

for marker in MARKERS:
    if marker not in content:
        fail(f"missing marker {marker}")

print("STAFF ASSIGNMENT LAYER CHECK PASSED")
