from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.schedule_state_models import ScheduleStateBlock

router = APIRouter(prefix="/api/day-control", tags=["day-control"])


def _staff_key(row: ScheduleStateBlock) -> str:
    if row.assigned_staff_id is not None:
        return f"staff-id:{row.assigned_staff_id}"
    return row.assigned_staff_name or row.assigned_role or row.who


def _resource_key(row: ScheduleStateBlock) -> str:
    return row.resource_id or row.resource_name or row.where


def _row(row: ScheduleStateBlock) -> dict[str, Any]:
    return {
        "id": row.id,
        "time": row.time,
        "lane": row.lane,
        "what": row.what,
        "who": row.who,
        "where": row.where,
        "status": row.status,
        "blocker": row.blocker,
        "next": row.next,
        "subject": row.subject,
        "assignedRole": row.assigned_role,
        "assignedStaffId": row.assigned_staff_id,
        "assignedStaffName": row.assigned_staff_name,
        "resourceId": row.resource_id,
        "resourceName": row.resource_name,
    }


@router.get("/conflicts")
def list_day_control_conflicts(session: Session = Depends(get_session)) -> dict[str, Any]:
    blocks = session.exec(select(ScheduleStateBlock).order_by(ScheduleStateBlock.time, ScheduleStateBlock.lane)).all()
    warnings: list[dict[str, Any]] = []

    by_time_resource: dict[tuple[str, str], list[ScheduleStateBlock]] = defaultdict(list)
    by_time_staff: dict[tuple[str, str], list[ScheduleStateBlock]] = defaultdict(list)

    for block in blocks:
        resource_key = _resource_key(block)
        staff_key = _staff_key(block)
        if resource_key and resource_key not in {"Reception", "Admin queue", "Client contact"}:
            by_time_resource[(block.time, resource_key)].append(block)
        if staff_key:
            by_time_staff[(block.time, staff_key)].append(block)
        if block.status in {"red", "amber"} and not (block.assigned_staff_name or block.assigned_staff_id or block.assigned_role or block.who):
            warnings.append({"type": "unassigned_work", "severity": "red", "title": f"Unassigned work at {block.time}", "detail": block.what, "blocks": [_row(block)]})
        if block.status in {"red", "amber"} and not (block.resource_name or block.resource_id or block.where):
            warnings.append({"type": "missing_resource", "severity": "red", "title": f"Missing resource at {block.time}", "detail": block.what, "blocks": [_row(block)]})
        if block.blocker != "none":
            warnings.append({"type": "blocker", "severity": "red" if block.status == "red" else "amber", "title": f"{block.time} {block.what}", "detail": f"{block.blocker} -> {block.next}", "blocks": [_row(block)]})
        if block.lane in {"insurance", "reception"} and block.blocker != "none":
            warnings.append({"type": "admin_blocker", "severity": "amber", "title": f"Admin unresolved: {block.subject or block.what}", "detail": f"{block.blocker} -> {block.next}", "blocks": [_row(block)]})
        if block.lane == "client" and block.blocker != "none":
            warnings.append({"type": "contact_update_blocked", "severity": "amber", "title": f"Contact update blocked: {block.subject or block.what}", "detail": f"{block.blocker} -> {block.next}", "blocks": [_row(block)]})

    for (time, resource), matching in by_time_resource.items():
        if len(matching) > 1:
            warnings.append({"type": "resource_clash", "severity": "red", "title": f"Resource clash at {time}: {resource}", "detail": " / ".join(block.what for block in matching), "blocks": [_row(block) for block in matching]})

    for (time, staff), matching in by_time_staff.items():
        if len(matching) > 1:
            warnings.append({"type": "staff_clash", "severity": "red", "title": f"Staff clash at {time}: {staff}", "detail": " / ".join(block.what for block in matching), "blocks": [_row(block) for block in matching]})

    return {"conflicts": warnings, "count": len(warnings)}
