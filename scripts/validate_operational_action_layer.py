from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    ROOT / "apps" / "web" / "lib" / "operational-actions.ts",
    ROOT / "apps" / "web" / "components" / "operational-detail-drawer.tsx",
    ROOT / "apps" / "web" / "components" / "bvs-flow-action-board.tsx",
    ROOT / "apps" / "api" / "app" / "workflow_action_routes.py",
]
MARKERS = [
    "recordOperationalAction",
    "OperationalDetailDrawer",
    "BvsFlowActionBoard",
    "OperationalRecordPayload",
    "record_operational_action",
]


def fail(message: str):
    print(f"ACTION LAYER CHECK FAILED: {message}")
    sys.exit(1)


content = ""
for path in FILES:
    if not path.exists():
        fail(f"missing {path.relative_to(ROOT)}")
    content += path.read_text(encoding="utf-8")

for marker in MARKERS:
    if marker not in content:
        fail(f"missing marker {marker}")

print("OPERATIONAL ACTION LAYER CHECK PASSED")
