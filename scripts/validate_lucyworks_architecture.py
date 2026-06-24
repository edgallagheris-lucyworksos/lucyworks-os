import subprocess
import sys

checks = [
    "scripts/validate_current_architecture.py",
    "scripts/validate_work_area_boards.py",
    "scripts/validate_staff_location_grid.py",
]

for check in checks:
    result = subprocess.call([sys.executable, check])
    if result:
        raise SystemExit(result)

raise SystemExit(0)
