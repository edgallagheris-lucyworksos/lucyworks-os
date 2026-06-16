import subprocess
import sys

raise SystemExit(subprocess.call([sys.executable, "scripts/validate_current_architecture.py"]))
