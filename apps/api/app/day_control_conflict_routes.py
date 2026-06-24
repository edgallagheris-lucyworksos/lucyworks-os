from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.schedule_state_models import ScheduleStateBlock

router = APIRouter(prefix="/api/day-control", tags=["day-control"])

ADMIN_RESOURCES = {"Reception", "Admin queue", "Client contact"}

PROCEDURE_PROFILES = {
    "mri": {"default": 90, "setup": 30, "handover": 30, "contingency": 30, "admin": 25, "label": "MRI referral pathway"},
    "ct": {"default": 60, "setup": 20, "handover": 20, "contingency": 20, "admin": 20, "label": "CT referral pathway"},
    "theatre": {"default": 150, "setup": 45, "handover": 45, "contingency": 60, "admin": 40, "label": "Major surgery referral pathway"},
    "recovery": {"default": 60, "setup": 10, "handover": 20, "contingency": 20, "admin": 10, "label": "Recovery monitoring"},
    "discharge": {"default": 30, "setup": 10, "handover": 10, "contingency": 15, "admin": 25, "label": "Referral discharge"},
    "consult": {"default": 45, "setup": 10, "handover": 15, "contingency": 20, "admin": 30, "label": "Referral consult"},
    "triage": {"default": 15, "setup": 5, "handover": 10, "contingency": 10, "admin": 10, "label": "Arrival triage"},
}


def _minutes(time_value: str) -> int:
    try:
        hour, minute = time_value.split(":", 1)
        return int(hour) * 60 + int(minute)
    except Exception:
        return 0


def _hhmm(minutes: int) -> str:
    minutes = max(0, minutes)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _profile(row: ScheduleStateBlock) -> dict[str, Any]:
    text = f"{row.what} {row.lane} {row.where} {row.next}".lower()
    if "mri" in text:
        return PROCEDURE_PROFILES["mri"]
    if "ct" in text:
        return PROCEDURE_PROFILES["ct"]
    if "theatre" in text or "surgery" in text or "surgical" in text:
        return PROCEDURE_PROFILES["theatre"]
    if "recovery" in text or "ward" in text:
        return PROCEDURE_PROFILES["recovery"]
    if "discharge" in text:
        return PROCEDURE_PROFILES["discharge"]
    if "consult" in text or "referral" in text:
        return PROCEDURE_PROFILES["consult"]
    if "arrival" in text or "triage" in text or "intake" in text:
        return PROCEDURE_PROFILES["triage"]
    return {"default": 15, "setup": 5, "handover": 5, "contingency": 5, "admin": 0, "label": "General work"}


def _protected_window(row: ScheduleStateBlock) -> tuple[int, int, dict[str, Any]]:
    profile = _profile(row)
    visible_start = _minutes(row.time)
    duration = row.duration_minutes or int(profile["default"])
    start = visible_start - int(profile["setup"])
    end = visible_start + duration + int(profile["handover"]) + int(profile["contingency"]) + int(profile["admin"])
    return start, end, profile


def _overlaps(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return left[0] < right[1] and right[0] < left[1]


def _same_case(left: ScheduleStateBlock, right: ScheduleStateBlock) -> bool:
    if left.episode_ref and right.episode_ref:
        return left.episode_ref == right.episode_ref
    if left.subject and right.subject:
        return left.subject == right.subject
    return False


def _staff_key(row: ScheduleStateBlock) -> str:
    if row.assigned_staff_id is not None:
        return f"staff-id:{row.assigned_staff_id}"
    return row.assigned_staff_name or row.assigned_role or row.who


def _resource_key(row: ScheduleStateBlock) -> str:
    return row.resource_id or row.resource_name or row.where


def _row(row: ScheduleStateBlock) -> dict[str, Any]:
    start, end, profile = _protected_window(row)
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
        "protectedStart": _hhmm(start),
        "protectedEnd": _hhmm(end),
        "protectedMinutes": max(0, end - start),
        "procedureProfile": profile["label"],
    }


def _protected_detail(left: ScheduleStateBlock, right: ScheduleStateBlock) -> str:
    left_start, left_end, left_profile = _protected_window(left)
    right_start, right_end, right_profile = _protected_window(right)
    return (
        f"{left.what} ({left_profile['label']}) protects {_hhmm(left_start)}-{_hhmm(left_end)}; "
        f"{right.what} ({right_profile['label']}) protects {_hhmm(right_start)}-{_hhmm(right_end)}"
    )


@router.get("/conflicts")
def list_day_control_conflicts(session: Session = Depends(get_session)) -> dict[str, Any]:
    blocks = session.exec(select(ScheduleStateBlock).order_by(ScheduleStateBlock.time, ScheduleStateBlock.lane)).all()
    warnings: list[dict[str, Any]] = []

    by_time_resource: dict[tuple[str, str], list[ScheduleStateBlock]] = defaultdict(list)
    by_time_staff: dict[tuple[str, str], list[ScheduleStateBlock]] = defaultdict(list)
    by_staff: dict[str, list[ScheduleStateBlock]] = defaultdict(list)
    by_resource: dict[str, list[ScheduleStateBlock]] = defaultdict(list)

    for block in blocks:
        resource_key = _resource_key(block)
        staff_key = _staff_key(block)
        if resource_key and resource_key not in ADMIN_RESOURCES:
            by_time_resource[(block.time, resource_key)].append(block)
            by_resource[resource_key].append(block)
        if staff_key:
            by_time_staff[(block.time, staff_key)].append(block)
            by_staff[staff_key].append(block)
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

    for staff, rows in by_staff.items():
        for index, left in enumerate(rows):
            left_window = _protected_window(left)[:2]
            for right in rows[index + 1 :]:
                if _overlaps(left_window, _protected_window(right)[:2]):
                    severity = "amber" if _same_case(left, right) else "red"
                    warnings.append({"type": "staff_protected_time_overlap", "severity": severity, "title": f"Protected staff time overlap: {staff}", "detail": _protected_detail(left, right), "blocks": [_row(left), _row(right)]})

    for resource, rows in by_resource.items():
        for index, left in enumerate(rows):
            left_window = _protected_window(left)[:2]
            for right in rows[index + 1 :]:
                if _overlaps(left_window, _protected_window(right)[:2]):
                    severity = "amber" if _same_case(left, right) else "red"
                    warnings.append({"type": "resource_protected_time_overlap", "severity": severity, "title": f"Protected resource time overlap: {resource}", "detail": _protected_detail(left, right), "blocks": [_row(left), _row(right)]})

    return {"conflicts": warnings, "count": len(warnings)}
