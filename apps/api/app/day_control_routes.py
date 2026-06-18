from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.database import get_session
from app.schedule_state_models import ScheduleStateBlock, ScheduleStateEvent

router = APIRouter(prefix="/api/day-control", tags=["day-control"])


class BlockPatch(BaseModel):
    time: str | None = None
    lane: str | None = None
    what: str | None = None
    who: str | None = None
    where: str | None = None
    how: str | None = None
    status: str | None = None
    blocker: str | None = None
    next: str | None = None
    route: str | None = None
    subject: str | None = None
    durationMinutes: int | None = None
    generatedFrom: str | None = None
    episodeRef: str | None = None
    assignedRole: str | None = None
    assignedStaffId: int | None = None
    assignedStaffName: str | None = None
    resourceId: str | None = None
    resourceName: str | None = None


class BlockCreate(BaseModel):
    id: str | None = None
    time: str
    lane: str
    what: str
    who: str
    where: str
    how: str
    status: str = "amber"
    blocker: str = "none"
    next: str = "continue planned flow"
    route: str = "/hospital-board"
    subject: str | None = None
    durationMinutes: int | None = None
    generatedFrom: str | None = None
    episodeRef: str | None = None
    assignedRole: str | None = None
    assignedStaffId: int | None = None
    assignedStaffName: str | None = None
    resourceId: str | None = None
    resourceName: str | None = None


class ActionPayload(BaseModel):
    action: str = Field(min_length=1)
    actor: str = "system"
    reason: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _payload_dict(payload: BaseModel, exclude_none: bool = False, exclude_unset: bool = False) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump(exclude_none=exclude_none, exclude_unset=exclude_unset)
    return payload.dict(exclude_none=exclude_none, exclude_unset=exclude_unset)


def _row_dict(row: ScheduleStateBlock) -> dict[str, Any]:
    return {"id": row.id, "time": row.time, "lane": row.lane, "what": row.what, "who": row.who, "where": row.where, "how": row.how, "status": row.status, "blocker": row.blocker, "next": row.next, "route": row.route, "subject": row.subject, "durationMinutes": row.duration_minutes, "generatedFrom": row.generated_from, "episodeRef": row.episode_ref, "assignedRole": row.assigned_role, "assignedStaffId": row.assigned_staff_id, "assignedStaffName": row.assigned_staff_name, "resourceId": row.resource_id, "resourceName": row.resource_name, "createdAt": row.created_at.isoformat() if row.created_at else None, "updatedAt": row.updated_at.isoformat() if row.updated_at else None}


def _make_row(data: dict[str, Any]) -> ScheduleStateBlock:
    return ScheduleStateBlock(id=str(data.get("id") or uuid4()), time=data["time"], lane=data["lane"], what=data["what"], who=data["who"], where=data["where"], how=data["how"], status=data.get("status", "amber"), blocker=data.get("blocker", "none"), next=data.get("next", "continue planned flow"), route=data.get("route", "/hospital-board"), subject=data.get("subject"), duration_minutes=data.get("durationMinutes"), generated_from=data.get("generatedFrom"), episode_ref=data.get("episodeRef"), assigned_role=data.get("assignedRole"), assigned_staff_id=data.get("assignedStaffId"), assigned_staff_name=data.get("assignedStaffName"), resource_id=data.get("resourceId"), resource_name=data.get("resourceName"), updated_at=_now())


def _set_patch_value(row: ScheduleStateBlock, key: str, value: Any) -> None:
    mapping = {"durationMinutes": "duration_minutes", "generatedFrom": "generated_from", "episodeRef": "episode_ref", "assignedRole": "assigned_role", "assignedStaffId": "assigned_staff_id", "assignedStaffName": "assigned_staff_name", "resourceId": "resource_id", "resourceName": "resource_name"}
    setattr(row, mapping.get(key, key), value)


def _add_event(session: Session, block_id: str, action: str, actor: str, before: dict[str, Any] | None, after: dict[str, Any] | None, reason: str | None = None) -> None:
    session.add(ScheduleStateEvent(block_id=block_id, action=action, actor=actor, reason=reason, before_json=json.dumps(before or {}), after_json=json.dumps(after or {})))


def _apply_action(row: ScheduleStateBlock, action: str) -> None:
    if action == "resolve": row.status = "green"; row.blocker = "none"; row.next = "complete or continue planned flow"
    elif action == "hold": row.status = "blue"; row.blocker = "on hold"; row.next = "review hold reason"
    elif action == "escalate": row.status = "red"; row.blocker = row.blocker if row.blocker != "none" else "escalated"; row.next = "senior review required"
    elif action == "request_review": row.status = "amber"; row.next = "review requested"
    elif action == "assign": row.status = "red" if row.status == "red" else "amber"; row.next = "owner assigned"
    elif action == "handover": row.status = "green"; row.blocker = "none"; row.next = "handover complete"
    elif action == "owner_update": row.status = "green"; row.blocker = "none"; row.next = "update recorded"
    else: row.status = "amber"; row.next = f"{action.replace('_', ' ')} requested"
    row.updated_at = _now()


@router.get("/blocks")
def list_blocks(session: Session = Depends(get_session)) -> dict[str, Any]:
    rows = session.exec(select(ScheduleStateBlock).order_by(ScheduleStateBlock.time, ScheduleStateBlock.lane)).all()
    return {"blocks": [_row_dict(row) for row in rows], "count": len(rows)}


@router.post("/blocks")
def create_block(payload: BlockCreate, session: Session = Depends(get_session)) -> dict[str, Any]:
    row = _make_row(_payload_dict(payload))
    session.add(row); session.commit(); session.refresh(row)
    after = _row_dict(row)
    _add_event(session, row.id, "create", "system", None, after); session.commit()
    return {"block": after}


@router.put("/blocks/bulk")
def replace_blocks(payload: dict[str, list[dict[str, Any]]], session: Session = Depends(get_session)) -> dict[str, Any]:
    for row in session.exec(select(ScheduleStateBlock)).all(): session.delete(row)
    session.commit()
    for block in payload.get("blocks", []): session.add(_make_row(block))
    session.commit()
    rows = session.exec(select(ScheduleStateBlock).order_by(ScheduleStateBlock.time, ScheduleStateBlock.lane)).all()
    after = {"count": len(rows)}
    _add_event(session, "bulk", "replace_blocks", "system", None, after); session.commit()
    return {"blocks": [_row_dict(row) for row in rows], "count": len(rows)}


@router.patch("/blocks/{block_id}")
def update_block(block_id: str, payload: BlockPatch, session: Session = Depends(get_session)) -> dict[str, Any]:
    row = session.get(ScheduleStateBlock, block_id)
    if not row: raise HTTPException(status_code=404, detail="block not found")
    before = _row_dict(row)
    for key, value in _payload_dict(payload, exclude_unset=True).items(): _set_patch_value(row, key, value)
    row.updated_at = _now(); session.add(row); session.commit(); session.refresh(row)
    after = _row_dict(row)
    _add_event(session, block_id, "update", "system", before, after); session.commit()
    return {"block": after}


@router.post("/blocks/{block_id}/actions")
def apply_action(block_id: str, payload: ActionPayload, session: Session = Depends(get_session)) -> dict[str, Any]:
    row = session.get(ScheduleStateBlock, block_id)
    if not row: raise HTTPException(status_code=404, detail="block not found")
    before = _row_dict(row)
    _apply_action(row, payload.action)
    session.add(row); session.commit(); session.refresh(row)
    after = _row_dict(row)
    _add_event(session, block_id, payload.action, payload.actor, before, after, payload.reason); session.commit()
    return {"block": after}


@router.get("/audit")
def list_audit(session: Session = Depends(get_session)) -> dict[str, Any]:
    rows = session.exec(select(ScheduleStateEvent).order_by(ScheduleStateEvent.created_at.desc()).limit(250)).all()
    audit = [{"id": row.id, "time": row.created_at.isoformat(), "blockId": row.block_id, "action": row.action, "actor": row.actor, "reason": row.reason, "before": json.loads(row.before_json or "{}"), "after": json.loads(row.after_json or "{}")} for row in rows]
    return {"audit": audit, "count": len(audit)}
