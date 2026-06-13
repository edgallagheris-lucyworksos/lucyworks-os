from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.models import AuditEvent, Handover, ResultReview, RoomState, ScheduleBlock, StaffMember, WorkItem

router = APIRouter(prefix="/api/actions", tags=["workflow-actions"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def write_audit(session: Session, actor: str, action: str, entity_type: str, entity_id: int, summary: str) -> AuditEvent:
    event = AuditEvent(actor_name=actor, action=action, entity_type=entity_type, entity_id=entity_id, summary=summary)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


class ActorPayload(BaseModel):
    actor_name: str = "LucyVet Workflow Engine"
    note: str = ""


class AssignPayload(BaseModel):
    owner_role: str
    owner_user_id: Optional[int] = None
    actor_name: str = "LucyVet Workflow Engine"
    note: str = ""


class ReviewResultPayload(BaseModel):
    actor_name: str = "LucyVet Workflow Engine"
    required_action: str = "Reviewed and actioned"
    note: str = ""


class ReleaseRoomPayload(BaseModel):
    room_name: str
    actor_name: str = "LucyVet Workflow Engine"
    next_episode_ref: Optional[str] = None
    note: str = ""


class MoveSchedulePayload(BaseModel):
    starts_at: datetime
    actor_name: str = "LucyVet Workflow Engine"
    note: str = ""


class OperationalRecordPayload(BaseModel):
    action: str
    target_id: str
    target_label: str
    target_type: str
    owner_role: Optional[str] = None
    blocker: Optional[str] = None
    next_action: Optional[str] = None
    actor_name: str = "LucyWorks Operator"
    note: str = ""


@router.post("/work-items/{work_item_id}/complete")
def complete_work_item(work_item_id: int, payload: ActorPayload, session: Session = Depends(get_session)):
    item = session.get(WorkItem, work_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Work item not found")
    item.status = "done"
    item.updated_at = utc_now()
    session.add(item)
    session.commit()
    session.refresh(item)
    event = write_audit(session, payload.actor_name, "work_item_completed", "work_item", item.id or 0, payload.note or item.title)
    return {"ok": True, "work_item": item, "audit_event": event}


@router.post("/work-items/{work_item_id}/assign")
def assign_work_item(work_item_id: int, payload: AssignPayload, session: Session = Depends(get_session)):
    item = session.get(WorkItem, work_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Work item not found")
    item.owner_role = payload.owner_role
    item.owner_user_id = payload.owner_user_id
    item.updated_at = utc_now()
    session.add(item)
    session.commit()
    session.refresh(item)
    event = write_audit(session, payload.actor_name, "work_item_assigned", "work_item", item.id or 0, payload.note or f"Assigned to {payload.owner_role}")
    return {"ok": True, "work_item": item, "audit_event": event}


@router.post("/work-items/{work_item_id}/accept")
def accept_work_item(work_item_id: int, payload: ActorPayload, session: Session = Depends(get_session)):
    item = session.get(WorkItem, work_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Work item not found")
    item.status = "accepted"
    item.updated_at = utc_now()
    session.add(item)
    session.commit()
    session.refresh(item)
    event = write_audit(session, payload.actor_name, "work_item_accepted", "work_item", item.id or 0, payload.note or item.title)
    return {"ok": True, "work_item": item, "audit_event": event}


@router.post("/work-items/{work_item_id}/decline")
def decline_work_item(work_item_id: int, payload: ActorPayload, session: Session = Depends(get_session)):
    item = session.get(WorkItem, work_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Work item not found")
    item.status = "new"
    item.owner_user_id = None
    item.updated_at = utc_now()
    session.add(item)
    session.commit()
    session.refresh(item)
    event = write_audit(session, payload.actor_name, "work_item_returned_to_role_queue", "work_item", item.id or 0, payload.note or item.title)
    return {"ok": True, "work_item": item, "audit_event": event}


@router.post("/handovers/{handover_id}/acknowledge")
def acknowledge_handover(handover_id: int, payload: ActorPayload, session: Session = Depends(get_session)):
    handover = session.get(Handover, handover_id)
    if not handover:
        raise HTTPException(status_code=404, detail="Handover not found")
    handover.acknowledged = True
    session.add(handover)
    session.commit()
    session.refresh(handover)
    event = write_audit(session, payload.actor_name, "handover_acknowledged", "handover", handover.id or 0, payload.note or handover.note)
    return {"ok": True, "handover": handover, "audit_event": event}


@router.post("/results/{result_id}/review")
def review_result(result_id: int, payload: ReviewResultPayload, session: Session = Depends(get_session)):
    result = session.get(ResultReview, result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result review not found")
    result.status = "reviewed"
    result.reviewed_at = utc_now()
    result.required_action = payload.required_action
    session.add(result)
    session.commit()
    session.refresh(result)
    event = write_audit(session, payload.actor_name, "result_reviewed", "result_review", result.id or 0, payload.note or payload.required_action)
    return {"ok": True, "result_review": result, "audit_event": event}


@router.post("/rooms/release")
def release_room(payload: ReleaseRoomPayload, session: Session = Depends(get_session)):
    room = session.exec(select(RoomState).where(RoomState.room_name == payload.room_name)).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room state not found")
    previous_episode = room.current_episode_ref
    room.state = "available"
    room.current_episode_ref = None
    room.next_episode_ref = payload.next_episode_ref
    room.cleaning_due_minutes = None
    session.add(room)
    session.commit()
    session.refresh(room)
    event = write_audit(session, payload.actor_name, "room_released", "room_state", room.id or 0, payload.note or f"Released {payload.room_name}; previous episode {previous_episode}")
    return {"ok": True, "room_state": room, "audit_event": event}


@router.post("/schedule-blocks/{block_id}/move")
def move_schedule_block(block_id: int, payload: MoveSchedulePayload, session: Session = Depends(get_session)):
    block = session.get(ScheduleBlock, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Schedule block not found")
    duration = block.ends_at - block.starts_at
    old_start = block.starts_at
    block.starts_at = payload.starts_at
    block.ends_at = payload.starts_at + duration
    session.add(block)
    session.commit()
    session.refresh(block)
    event = write_audit(session, payload.actor_name, "schedule_block_moved", "schedule_block", block.id or 0, payload.note or f"Moved from {old_start.isoformat()} to {block.starts_at.isoformat()}")
    return {"ok": True, "schedule_block": block, "audit_event": event}


@router.post("/schedule-blocks/{block_id}/delay-chain")
def delay_schedule_chain(block_id: int, minutes: int = 15, actor_name: str = "LucyVet Workflow Engine", session: Session = Depends(get_session)):
    block = session.get(ScheduleBlock, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Schedule block not found")
    delta = timedelta(minutes=minutes)
    chain = session.exec(select(ScheduleBlock).where(ScheduleBlock.case_procedure_id == block.case_procedure_id).order_by(ScheduleBlock.starts_at)).all()
    moved: list[int] = []
    for item in chain:
        if item.starts_at >= block.starts_at:
            item.starts_at = item.starts_at + delta
            item.ends_at = item.ends_at + delta
            session.add(item)
            if item.id is not None:
                moved.append(item.id)
    session.commit()
    event = write_audit(session, actor_name, "schedule_chain_delayed", "case_procedure", block.case_procedure_id, f"Delayed blocks {moved} by {minutes} minutes")
    return {"ok": True, "moved_block_ids": moved, "delay_minutes": minutes, "audit_event": event}


@router.post("/operational/record")
def record_operational_action(payload: OperationalRecordPayload, session: Session = Depends(get_session)):
    summary = payload.note or f"{payload.action} {payload.target_label}; owner {payload.owner_role or 'unassigned'}; blocker {payload.blocker or 'none'}; next {payload.next_action or 'not set'}"
    event = write_audit(session, payload.actor_name, f"operational_{payload.action}", payload.target_type, 0, summary)
    return {"ok": True, "audit_event": event, "target_id": payload.target_id}


@router.get("/assignable-staff")
def assignable_staff(role: Optional[str] = None, session: Session = Depends(get_session)):
    rows = session.exec(select(StaffMember).where(StaffMember.active == True).order_by(StaffMember.role, StaffMember.name)).all()
    if role:
        rows = [row for row in rows if row.role == role]
    return {"count": len(rows), "staff": rows}
