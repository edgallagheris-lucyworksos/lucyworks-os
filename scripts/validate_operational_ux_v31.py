#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web"

result = subprocess.run(
    [sys.executable, str(ROOT / "scripts" / "audit_operational_ux.py")],
    cwd=ROOT,
    text=True,
    capture_output=True,
)
print(result.stdout)
if result.stderr:
    print(result.stderr, file=sys.stderr)
if result.returncode:
    raise SystemExit(result.returncode)
if "ERROR: 0" not in result.stdout or "WARN: 0" not in result.stdout:
    raise SystemExit("V31 requires zero operational UX audit findings")

required_markers = {
    WEB / "components" / "guided-referral-intake-v31.tsx": [
        "Patient and duplicate check",
        "Owner and authority",
        "Referral source",
        "Clinical need and urgency",
        "Documents and review",
        "Confirmation and next action",
        "requiresIdentityReview",
    ],
    WEB / "components" / "episode-selection-bridge-v31.tsx": [
        "lucyworks:selected-episode",
        "/patient-record",
        "/clinical-execution",
        "/episode-command",
    ],
    WEB / "components" / "technical-surface-boundary-v31.tsx": [
        "Technical administration surface",
        "Legacy compatibility surface",
        "Patient Command",
        "Hospital Today",
    ],
    WEB / "lib" / "evidence-dialog.ts": [
        'role", "dialog"',
        'aria-modal",
        "Confirm evidence",
        "min-height:48px",
    ],
    WEB / "app" / "layout.tsx": ["EpisodeSelectionBridgeV31", "TechnicalSurfaceBoundaryV31"],
    WEB / "app" / "referral-intake" / "page.tsx": ["GuidedReferralIntakeV31"],
}
for path, markers in required_markers.items():
    text = path.read_text(encoding="utf-8")
    missing = [marker for marker in markers if marker not in text]
    if missing:
        raise SystemExit(f"{path.relative_to(ROOT)} missing v31 markers: {missing}")

public_auth = {
    "apps/web/app/login/page.tsx",
    "apps/web/app/auth/callback/page.tsx",
}
for path in WEB.rglob("*.tsx"):
    rel = str(path.relative_to(ROOT))
    text = path.read_text(encoding="utf-8")
    if rel not in public_auth and "fetch(`${API_BASE}" in text:
        raise SystemExit(f"Authenticated API bypass remains: {rel}")
    if "window.prompt(" in text or "window.alert(" in text:
        raise SystemExit(f"Native browser dialog remains: {rel}")
    if "new Date().toISOString().slice(0, 10)" in text:
        raise SystemExit(f"UTC operating date remains: {rel}")

primary = [
    WEB / "components" / "operational-workspace-v16.tsx",
    WEB / "components" / "care-brief-v16.tsx",
    WEB / "components" / "responsive-hospital-board-v15.tsx",
    WEB / "components" / "guided-referral-intake-v31.tsx",
]
for path in primary:
    text = path.read_text(encoding="utf-8").lower()
    suspicious = [token for token in ("silently use seed", "seed snapshot fallback", "fallback to mock", "fallback to demo") if token in text]
    if suspicious:
        raise SystemExit(f"Primary surface contains silent fallback marker: {path.relative_to(ROOT)} {suspicious}")

print("OPERATIONAL_UX_REAL_UAT_V31_VALIDATION_PASSED")
