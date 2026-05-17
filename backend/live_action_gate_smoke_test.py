"""Compatibility shim for legacy CI.

The real live-action gate smoke test now lives in apps/api. Older workflows
still execute this file from backend/, so forward to the monorepo version
instead of using the stale backend app copy.
"""

from pathlib import Path
import os
import runpy
import sys

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
TARGET = API_DIR / Path(__file__).name

if not TARGET.exists():
    raise FileNotFoundError(f"Expected monorepo smoke test missing: {TARGET}")

os.chdir(API_DIR)
sys.path.insert(0, str(API_DIR))
runpy.run_path(str(TARGET), run_name="__main__")
