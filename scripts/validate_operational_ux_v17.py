#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

checks = {
    "apps/web/components/hospital-master-board-v11.tsx": [
        "getTimezoneOffset()",
    ],
    "apps/web/components/hospital-command-workspace.tsx": [
        'new URLSearchParams(window.location.search).get("episode")',
        "/care?episode=",
        "Reason for the next decision or transition",
        "One risk per line",
        "Senior approve with reason",
    ],
    "apps/web/components/detailed-patient-record-workspace.tsx": [
        'new URLSearchParams(window.location.search).get("episode")',
        "position: \"sticky\"",
        "/clinical-execution?episode=",
    ],
    "apps/web/app/clinical-execution/page.tsx": [
        'new URLSearchParams(window.location.search).get("episode")',
        "localDateTimeInput()",
        "Administration evidence",
        "Clinical observation notes",
        "Critical result requiring acknowledgement",
        "Controlled-drug discrepancy evidence",
        "Approval evidence",
    ],
}

errors: list[str] = []
for rel, markers in checks.items():
    path = ROOT / rel
    if not path.exists():
        errors.append(f"missing {rel}")
        continue
    text = path.read_text(encoding="utf-8")
    for marker in markers:
        if marker not in text:
            errors.append(f"{rel}: missing marker {marker!r}")

for rel in [
    "apps/web/components/hospital-command-workspace.tsx",
    "apps/web/app/clinical-execution/page.tsx",
]:
    text = (ROOT / rel).read_text(encoding="utf-8")
    for forbidden in ["window.prompt(", "window.alert(", "window.confirm("]:
        if forbidden in text:
            errors.append(f"{rel}: forbidden browser dialog {forbidden}")

board = (ROOT / "apps/web/components/hospital-master-board-v11.tsx").read_text(encoding="utf-8")
if "return new Date().toISOString().slice(0, 10);" in board:
    errors.append("master board still derives operating date from UTC")

if errors:
    print("\n--- OPERATIONAL UX V17 VALIDATION FAILED ---")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print("OPERATIONAL UX V17 VALIDATION PASSED")
