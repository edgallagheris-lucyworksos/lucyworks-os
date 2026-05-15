from __future__ import annotations

from typing import Any
from sqlmodel import Session


def dashboard_integrity_report(session: Session, dashboard: dict[str, Any]) -> dict[str, Any]:
    """
    Lightweight integrity report for the 15-minute operational dashboard.

    This module exists so dashboard routes can load reliably and so the board can
    surface data-quality problems instead of silently pretending everything is OK.
    """
    slots = dashboard.get("slots", []) or []
    rooms = dashboard.get("rooms", []) or []
    summary = dashboard.get("summary", {}) or {}

    issues: list[dict[str, Any]] = []

    if not slots:
        issues.append({
            "severity": "high",
            "code": "NO_SLOTS",
            "message": "No 15-minute slots generated for the hospital board.",
            "action": "Check dashboard schedule generation and ScheduleBlock data.",
        })

    if not rooms:
        issues.append({
            "severity": "medium",
            "code": "NO_ROOMS",
            "message": "No rooms are available on the dashboard.",
            "action": "Run first-run seed or add RoomState records.",
        })

    for slot in slots:
        for block in slot.get("blocks", []) or []:
            block_id = block.get("block_id")
            if not block.get("episode") and block.get("block_type") not in {"cleaning", "turnover", "admin"}:
                issues.append({
                    "severity": "medium",
                    "code": "BLOCK_WITHOUT_EPISODE",
                    "message": f"Schedule block {block_id} is not linked to an episode.",
                    "action": "Attach the block to an Episode/Case or mark it as cleaning/admin.",
                })
            if not block.get("owner_role"):
                issues.append({
                    "severity": "medium",
                    "code": "BLOCK_WITHOUT_OWNER_ROLE",
                    "message": f"Schedule block {block_id} has no owner role.",
                    "action": "Assign an owner role so the board can create responsibility.",
                })
            pressure = block.get("pressure", {}) or {}
            if pressure.get("hard_blocks"):
                issues.append({
                    "severity": "high",
                    "code": "HARD_BLOCK_PRESENT",
                    "message": f"Schedule block {block_id} has hard blockers.",
                    "action": "Open the block/case and resolve the blocker before progression.",
                    "count": len(pressure.get("hard_blocks", [])),
                })

    high_count = len([i for i in issues if i["severity"] == "high"])
    medium_count = len([i for i in issues if i["severity"] == "medium"])

    return {
        "status": "fail" if high_count else "warning" if medium_count else "pass",
        "high_count": high_count,
        "medium_count": medium_count,
        "issue_count": len(issues),
        "summary_checked": summary,
        "issues": issues[:100],
    }
