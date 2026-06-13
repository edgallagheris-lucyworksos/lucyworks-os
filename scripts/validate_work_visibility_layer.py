from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    ROOT / "apps" / "api" / "app" / "workflow_action_routes.py",
    ROOT / "apps" / "web" / "components" / "my-assigned-work-board.tsx",
    ROOT / "apps" / "web" / "app" / "my-shift" / "page.tsx",
]
MARKERS = [
    "work_item_accepted",
    "work_item_returned_to_role_queue",
    "MyAssignedWorkBoard",
    "/api/role-queues/my-shift",
    "owner_user_id",
]


def fail(message: str):
    print(f"WORK VISIBILITY CHECK FAILED: {message}")
    sys.exit(1)


content = ""
for path in FILES:
    if not path.exists():
        fail(f"missing {path.relative_to(ROOT)}")
    content += path.read_text(encoding="utf-8")

for marker in MARKERS:
    if marker not in content:
        fail(f"missing marker {marker}")

print("WORK VISIBILITY LAYER CHECK PASSED")
