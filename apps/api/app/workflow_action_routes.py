from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.models import AuditEvent, Handover, ResultReview, RoomState, ScheduleBlock, StaffMember, WorkItem

router = APIRouter(prefix="/api/actions", tags=["workflow-actions"])

def _row(model):
    return {field: getattr(model, field) for field in model.__class__.model_fields}


class AssignWorkItemRequest(BaseModel):
    owner_user_id: int | None = None
    owner_role: str


class ReleaseRoomRequest(BaseModel):
    room_state_id: int


class MoveScheduleBlockRequest(BaseModel):
    starts_at: datetime
    ends_at: datetime
    room_name: str | None = None
    assigned_staff_member_id: int | None = None


class DelayChainRequest(BaseModel):
    minutes: int = 15


def _audit(session: Session, *, action: str, entity_type: str, entity_id: int, summary: str) -> AuditEvent:
    event = AuditEvent(
        actor_name="workflow-actions",
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary=summary,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@router.post("/work-items/{work_item_id}/complete")
def complete_work_item(work_item_id: int, session: Session = Depends(get_session)):
    item = session.get(WorkItem, work_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="WorkItem not found")
    item.status = "done"
    session.add(item)
    session.commit()
    session.refresh(item)
    _audit(session, action="work_item.complete", entity_type="WorkItem", entity_id=item.id, summary=f"Work item {item.id} marked done")
    return {"ok": True, "work_item": _row(item)}


@router.post("/work-items/{work_item_id}/assign")
def assign_work_item(work_item_id: int, payload: AssignWorkItemRequest, session: Session = Depends(get_session)):
    item = session.get(WorkItem, work_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="WorkItem not found")
    item.owner_role = payload.owner_role
    item.owner_user_id = payload.owner_user_id
    session.add(item)
    session.commit()
    session.refresh(item)
    _audit(session, action="work_item.assign", entity_type="WorkItem", entity_id=item.id, summary=f"Work item {item.id} assigned to role {item.owner_role}")
    return {"ok": True, "work_item": _row(item)}


@router.post("/handovers/{handover_id}/acknowledge")
def acknowledge_handover(handover_id: int, session: Session = Depends(get_session)):
    handover = session.get(Handover, handover_id)
    if not handover:
        raise HTTPException(status_code=404, detail="Handover not found")
    handover.acknowledged = True
    session.add(handover)
    session.commit()
    session.refresh(handover)
    _audit(session, action="handover.acknowledge", entity_type="Handover", entity_id=handover.id, summary=f"Handover {handover.id} acknowledged")
    return {"ok": True, "handover": _row(handover)}


@router.post("/results/{result_id}/review")
def review_result(result_id: int, session: Session = Depends(get_session)):
    result = session.get(ResultReview, result_id)
    if not result:
        raise HTTPException(status_code=404, detail="ResultReview not found")
    result.status = "reviewed"
    session.add(result)
    session.commit()
    session.refresh(result)
    _audit(session, action="result.review", entity_type="ResultReview", entity_id=result.id, summary=f"Result review {result.id} marked reviewed")
    return {"ok": True, "result_review": _row(result)}


@router.post("/rooms/release")
def release_room(payload: ReleaseRoomRequest, session: Session = Depends(get_session)):
    room = session.get(RoomState, payload.room_state_id)
    if not room:
        raise HTTPException(status_code=404, detail="RoomState not found")
    room.state = "available"
    room.current_episode_ref = None
    session.add(room)
    session.commit()
    session.refresh(room)
    _audit(session, action="room.release", entity_type="RoomState", entity_id=room.id, summary=f"Room {room.room_name} released")
    return {"ok": True, "room_state": _row(room)}


@router.post("/schedule-blocks/{block_id}/move")
def move_schedule_block(block_id: int, payload: MoveScheduleBlockRequest, session: Session = Depends(get_session)):
    block = session.get(ScheduleBlock, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="ScheduleBlock not found")
    block.starts_at = payload.starts_at
    block.ends_at = payload.ends_at
    if payload.room_name is not None:
        block.room_name = payload.room_name
    if payload.assigned_staff_member_id is not None:
        block.assigned_staff_member_id = payload.assigned_staff_member_id
    session.add(block)
    session.commit()
    session.refresh(block)
    _audit(session, action="schedule_block.move", entity_type="ScheduleBlock", entity_id=block.id, summary=f"Schedule block {block.id} moved")
    return {"ok": True, "schedule_block": _row(block)}


@router.post("/schedule-blocks/{block_id}/delay-chain")
def delay_chain(block_id: int, payload: DelayChainRequest, session: Session = Depends(get_session)):
    block = session.get(ScheduleBlock, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="ScheduleBlock not found")

    blocks = session.exec(
        select(ScheduleBlock)
        .where(ScheduleBlock.room_name == block.room_name)
        .where(ScheduleBlock.starts_at >= block.starts_at)
        .order_by(ScheduleBlock.starts_at)
    ).all()
    for each in blocks:
        each.starts_at = each.starts_at + timedelta(minutes=payload.minutes)
        each.ends_at = each.ends_at + timedelta(minutes=payload.minutes)
        session.add(each)

    session.commit()
    session.refresh(block)
    _audit(session, action="schedule_block.delay_chain", entity_type="ScheduleBlock", entity_id=block.id, summary=f"Delay chain from block {block.id} by {payload.minutes} minutes")
    return {"ok": True, "schedule_block": _row(block)}


@router.get("/assignable-staff")
def assignable_staff(session: Session = Depends(get_session)):
    staff = session.exec(select(StaffMember).where(StaffMember.active == True)).all()
    return {"ok": True, "assignable_staff": [_row(member) for member in staff]}
