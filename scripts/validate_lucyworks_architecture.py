import subprocess
import sys

checks = [
    "scripts/validate_current_architecture.py",
    "scripts/validate_work_area_boards.py",
]

for check in checks:
    result = subprocess.call([sys.executable, check])
    if result:
        raise SystemExit(result)

raise SystemExit(0)
