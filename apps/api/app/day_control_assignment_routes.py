from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.assignment_directory_models import AssignmentPersonOption, AssignmentResourceOption
from app.database import get_session
from app.schedule_state_models import ScheduleStateBlock, ScheduleStateEvent

router = APIRouter(prefix="/api/day-control", tags=["day-control-assignment"])

PROCEDURE_PROFILES = {
    "mri": {"default": 90, "setup": 30, "handover": 30, "contingency": 30, "admin": 25, "label": "MRI referral pathway"},
    "ct": {"default": 60, "setup": 20, "handover": 20, "contingency": 20, "admin": 20, "label": "CT referral pathway"},
    "theatre": {"default": 150, "setup": 45, "handover": 45, "contingency": 60, "admin": 40, "label": "Major surgery referral pathway"},
    "recovery": {"default": 60, "setup": 10, "handover": 20, "contingency": 20, "admin": 10, "label": "Recovery monitoring"},
    "discharge": {"default": 30, "setup": 10, "handover": 10, "contingency": 15, "admin": 25, "label": "Referral discharge"},
    "consult": {"default": 45, "setup": 10, "handover": 15, "contingency": 20, "admin": 30, "label": "Referral consult"},
    "triage": {"default": 15, "setup": 5, "handover": 10, "contingency": 10, "admin": 10, "label": "Arrival triage"},
}


class AssignmentRecommendationRequest(BaseModel):
    blockId: str


class SafeAssignPayload(BaseModel):
    assignedStaffId: int | None = None
    assignedStaffName: str | None = None
    assignedRole: str | None = None
    resourceId: str | None = None
    resourceName: str | None = None
    allowWarning: bool = False
    actor: str = "frontend"
    reason: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


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


def _text(row: ScheduleStateBlock) -> str:
    return f"{row.assigned_role or ''} {row.who or ''} {row.what or ''} {row.where or ''} {row.how or ''} {row.next or ''} {row.lane or ''}".lower()


def _row_dict(row: ScheduleStateBlock) -> dict[str, Any]:
    start, end, profile = _protected_window(row)
    return {"id": row.id, "time": row.time, "lane": row.lane, "what": row.what, "who": row.who, "where": row.where, "how": row.how, "status": row.status, "blocker": row.blocker, "next": row.next, "route": row.route, "subject": row.subject, "durationMinutes": row.duration_minutes, "generatedFrom": row.generated_from, "episodeRef": row.episode_ref, "assignedRole": row.assigned_role, "assignedStaffId": row.assigned_staff_id, "assignedStaffName": row.assigned_staff_name, "resourceId": row.resource_id, "resourceName": row.resource_name, "protectedStart": _hhmm(start), "protectedEnd": _hhmm(end), "protectedMinutes": max(0, end - start), "procedureProfile": profile["label"]}


def _person(row: AssignmentPersonOption) -> dict[str, Any]:
    return {"id": row.id, "name": row.name, "role": row.role, "area": row.area, "active": row.active}


def _resource(row: AssignmentResourceOption) -> dict[str, Any]:
    return {"id": row.id, "name": row.name, "type": row.type, "active": row.active}


def _staff_matches(person: AssignmentPersonOption, row: ScheduleStateBlock) -> bool:
    return row.assigned_staff_id == person.id or (row.assigned_staff_name or "").lower() == person.name.lower()


def _resource_matches(resource: AssignmentResourceOption, row: ScheduleStateBlock) -> bool:
    return row.resource_id == resource.id or (row.resource_name or row.where or "").lower() == resource.name.lower()


def _staff_score(block: ScheduleStateBlock, person: AssignmentPersonOption) -> tuple[int, list[str]]:
    haystack = _text(block)
    role = f"{person.role} {person.area}".lower()
    reasons: list[str] = []
    score = 0
    if block.assigned_role and block.assigned_role.lower() in role:
        score += 8; reasons.append("role match")
    if block.who and block.who.lower() in role:
        score += 6; reasons.append("owner role match")
    if person.area and person.area.lower() in haystack:
        score += 4; reasons.append("area match")
    if "mri" in haystack and "imaging" in role:
        score += 6; reasons.append("imaging fit")
    if "ct" in haystack and "imaging" in role:
        score += 6; reasons.append("imaging fit")
    if ("theatre" in haystack or "surgery" in haystack or "surgical" in haystack) and ("surgical" in role or "surgeon" in role or "theatre" in role):
        score += 6; reasons.append("theatre fit")
    if ("anaesthesia" in haystack or "anaes" in haystack or "sedation" in haystack or "induction" in haystack) and "anaesthesia" in role:
        score += 6; reasons.append("anaesthesia fit")
    if ("ward" in haystack or "recovery" in haystack or "nursing" in haystack) and "nurse" in role:
        score += 6; reasons.append("ward/recovery fit")
    if ("consent" in haystack or "estimate" in haystack or "insurance" in haystack or "owner" in haystack or "client" in haystack) and ("admin" in role or "reception" in role or "client contact" in role or "insurance" in role):
        score += 6; reasons.append("admin/client fit")
    if "pharmacy" in haystack and "pharmacy" in role:
        score += 6; reasons.append("pharmacy fit")
    return score, reasons


def _resource_score(block: ScheduleStateBlock, resource: AssignmentResourceOption) -> tuple[int, list[str]]:
    haystack = _text(block)
    source = f"{resource.name} {resource.type}".lower()
    reasons: list[str] = []
    score = 0
    if block.where and block.where.lower() in source:
        score += 8; reasons.append("location match")
    if block.resource_name and block.resource_name.lower() in source:
        score += 8; reasons.append("resource match")
    if "mri" in haystack and "mri" in source:
        score += 7; reasons.append("MRI fit")
    if "ct" in haystack and "ct" in source:
        score += 7; reasons.append("CT fit")
    if ("theatre" in haystack or "surgery" in haystack or "surgical" in haystack) and "theatre" in source:
        score += 7; reasons.append("theatre fit")
    if ("ward" in haystack or "recovery" in haystack) and ("ward" in source or "recovery" in source):
        score += 6; reasons.append("ward/recovery fit")
    if ("consult" in haystack or "owner" in haystack or "client" in haystack) and ("consult" in source or "client" in source):
        score += 4; reasons.append("client/consult fit")
    return score, reasons


def _conflict_for(block: ScheduleStateBlock, rows: list[ScheduleStateBlock], matcher) -> dict[str, Any] | None:
    target = _protected_window(block)[:2]
    clashes = [row for row in rows if row.id != block.id and matcher(row) and not _same_case(block, row) and _overlaps(target, _protected_window(row)[:2])]
    if not clashes:
        return None
    latest = max(_protected_window(row)[1] for row in clashes)
    return {"busyUntil": _hhmm(latest), "with": [row.subject or row.what for row in clashes], "detail": " / ".join(row.subject or row.what for row in clashes)}


def _candidate_staff(block: ScheduleStateBlock, rows: list[ScheduleStateBlock], session: Session) -> list[dict[str, Any]]:
    people = session.exec(select(AssignmentPersonOption).where(AssignmentPersonOption.active == True).order_by(AssignmentPersonOption.area, AssignmentPersonOption.name)).all()
    candidates = []
    for person in people:
        score, reasons = _staff_score(block, person)
        conflict = _conflict_for(block, rows, lambda row, person=person: _staff_matches(person, row))
        if score > 0 or not conflict:
            candidates.append({"person": _person(person), "score": score, "reasons": reasons, "conflict": conflict, "recommended": False})
    candidates.sort(key=lambda item: (bool(item["conflict"]), -int(item["score"]), item["person"]["name"]))
    for item in candidates:
        if not item["conflict"]:
            item["recommended"] = True
            break
    return candidates[:12]


def _candidate_resources(block: ScheduleStateBlock, rows: list[ScheduleStateBlock], session: Session) -> list[dict[str, Any]]:
    resources = session.exec(select(AssignmentResourceOption).where(AssignmentResourceOption.active == True).order_by(AssignmentResourceOption.type, AssignmentResourceOption.name)).all()
    candidates = []
    for resource in resources:
        score, reasons = _resource_score(block, resource)
        conflict = _conflict_for(block, rows, lambda row, resource=resource: _resource_matches(resource, row))
        if score > 0 or not conflict:
            candidates.append({"resource": _resource(resource), "score": score, "reasons": reasons, "conflict": conflict, "recommended": False})
    candidates.sort(key=lambda item: (bool(item["conflict"]), -int(item["score"]), item["resource"]["name"]))
    for item in candidates:
        if not item["conflict"]:
            item["recommended"] = True
            break
    return candidates[:12]


def _assignment_warnings(block: ScheduleStateBlock, payload: SafeAssignPayload, rows: list[ScheduleStateBlock], session: Session) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    if payload.assignedStaffId is not None:
        person = session.get(AssignmentPersonOption, payload.assignedStaffId)
        if person:
            conflict = _conflict_for(block, rows, lambda row: _staff_matches(person, row))
            if conflict:
                warnings.append({"type": "staff_protected_time_overlap", "severity": "warn", "message": f"{person.name} busy until {conflict['busyUntil']}", "conflict": conflict})
    if payload.resourceId:
        resource = session.get(AssignmentResourceOption, payload.resourceId)
        if resource:
            conflict = _conflict_for(block, rows, lambda row: _resource_matches(resource, row))
            if conflict:
                warnings.append({"type": "resource_protected_time_overlap", "severity": "warn", "message": f"{resource.name} busy until {conflict['busyUntil']}", "conflict": conflict})
    return warnings


def _add_event(session: Session, block_id: str, action: str, actor: str, before: dict[str, Any], after: dict[str, Any], reason: str | None = None) -> None:
    session.add(ScheduleStateEvent(block_id=block_id, action=action, actor=actor, reason=reason, before_json=json.dumps(before), after_json=json.dumps(after)))


@router.post("/assignment-recommendations")
def assignment_recommendations(payload: AssignmentRecommendationRequest, session: Session = Depends(get_session)) -> dict[str, Any]:
    block = session.get(ScheduleStateBlock, payload.blockId)
    if not block:
        raise HTTPException(status_code=404, detail="block not found")
    rows = session.exec(select(ScheduleStateBlock).order_by(ScheduleStateBlock.time, ScheduleStateBlock.lane)).all()
    start, end, profile = _protected_window(block)
    return {"block": _row_dict(block), "decision": "recommend", "protectedWindow": {"start": _hhmm(start), "end": _hhmm(end), "minutes": max(0, end - start), "profile": profile["label"]}, "staff": _candidate_staff(block, rows, session), "resources": _candidate_resources(block, rows, session)}


@router.patch("/blocks/{block_id}/safe-assign")
def safe_assign_block(block_id: str, payload: SafeAssignPayload, session: Session = Depends(get_session)) -> dict[str, Any]:
    block = session.get(ScheduleStateBlock, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="block not found")
    rows = session.exec(select(ScheduleStateBlock).order_by(ScheduleStateBlock.time, ScheduleStateBlock.lane)).all()
    warnings = _assignment_warnings(block, payload, rows, session)
    decision = "warn" if warnings else "allow"
    before = _row_dict(block)
    if warnings and not payload.allowWarning:
        return {"decision": decision, "allowed": False, "warnings": warnings, "block": before, "staff": _candidate_staff(block, rows, session), "resources": _candidate_resources(block, rows, session)}

    block.assigned_staff_id = payload.assignedStaffId
    block.assigned_staff_name = payload.assignedStaffName
    block.assigned_role = payload.assignedRole or block.assigned_role or block.who
    block.resource_id = payload.resourceId
    block.resource_name = payload.resourceName
    block.status = "amber" if block.status != "red" else "red"
    block.next = "safe assignment warning accepted" if warnings else "safe assignment updated"
    block.updated_at = _now()
    session.add(block)
    session.commit()
    session.refresh(block)
    after = _row_dict(block)
    _add_event(session, block_id, "safe_assign", payload.actor, before, after, payload.reason or ("; ".join(item["message"] for item in warnings) if warnings else "safe assignment"))
    session.commit()
    return {"decision": decision, "allowed": True, "warnings": warnings, "block": after, "staff": _candidate_staff(block, rows, session), "resources": _candidate_resources(block, rows, session)}
