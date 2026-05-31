from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core_machine_routes import detect_conflicts
from app.database import get_session
from app.models import AuditEvent, CaseProcedure, Episode, ProcedureType, ScheduleBlock

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def snap_to_quarter(dt: datetime) -> datetime:
    minute = (dt.minute // 15) * 15
    return dt.replace(minute=minute, second=0, microsecond=0)


def row(obj: Any) -> dict[str, Any]:
    fields = getattr(obj, "model_fields", {})
    return {name: getattr(obj, name) for name in fields}


def write_audit(session: Session, actor: str, action: str, entity_type: str, entity_id: int, summary: str) -> AuditEvent:
    event = AuditEvent(actor_name=actor, action=action, entity_type=entity_type, entity_id=entity_id, summary=summary)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


class GenerateChainPayload(BaseModel):
    episode_id: Optional[int] = None
    episode_ref: Optional[str] = None
    procedure_type_id: int
    room_name: str
    starts_at: datetime
    assigned_staff_member_id: Optional[int] = None
    actor_name: str = "LucyVet Scheduler"


class MoveChainPayload(BaseModel):
    starts_at: datetime
    actor_name: str = "LucyVet Scheduler"


class DelayChainPayload(BaseModel):
    minutes: int = 15
    actor_name: str = "LucyVet Scheduler"


def resolve_episode(session: Session, payload: GenerateChainPayload) -> Episode:
    if payload.episode_id:
        episode = session.get(Episode, payload.episode_id)
        if episode:
            return episode
    if payload.episode_ref:
        episode = session.exec(select(Episode).where(Episode.episode_ref == payload.episode_ref)).first()
        if episode:
            return episode
    raise HTTPException(status_code=404, detail="Episode not found")


def block_chain(session: Session, case_procedure_id: int) -> list[ScheduleBlock]:
    return session.exec(
        select(ScheduleBlock)
        .where(ScheduleBlock.case_procedure_id == case_procedure_id)
        .order_by(ScheduleBlock.starts_at)
    ).all()


def serialise_chain(session: Session, case_procedure_id: int) -> dict[str, Any]:
    cp = session.get(CaseProcedure, case_procedure_id)
    if not cp:
        raise HTTPException(status_code=404, detail="Case procedure not found")
    return {
        "case_procedure": row(cp),
        "blocks": [row(block) for block in block_chain(session, case_procedure_id)],
        "conflicts": detect_conflicts(session),
    }


def create_schedule_blocks(
    session: Session,
    *,
    case_procedure: CaseProcedure,
    procedure_type: ProcedureType,
    room_name: str,
    starts_at: datetime,
    assigned_staff_member_id: Optional[int],
) -> list[ScheduleBlock]:
    chain = [
        ("prep", procedure_type.prep_min, "nurse", None),
        ("anaesthesia", procedure_type.anaesthesia_min, "clinician", assigned_staff_member_id),
        ("procedure", procedure_type.default_duration_min, "clinician", assigned_staff_member_id),
        ("recovery", procedure_type.recovery_min, "nurse", None),
        ("cleaning", procedure_type.cleaning_min, "pca", None),
    ]
    cursor = snap_to_quarter(starts_at)
    created: list[ScheduleBlock] = []
    for block_type, minutes, owner_role, staff_id in chain:
        block = ScheduleBlock(
            episode_id=case_procedure.episode_id,
            case_procedure_id=case_procedure.id or 0,
            block_type=block_type,
            room_name=room_name,
            owner_role=owner_role,
            assigned_staff_member_id=staff_id,
            starts_at=cursor,
            ends_at=cursor + timedelta(minutes=minutes),
            status="planned",
        )
        session.add(block)
        session.flush()
        created.append(block)
        cursor = block.ends_at
    return created


@router.post("/chains/generate")
def generate_chain(payload: GenerateChainPayload, session: Session = Depends(get_session)):
    episode = resolve_episode(session, payload)
    procedure_type = session.get(ProcedureType, payload.procedure_type_id)
    if not procedure_type:
        raise HTTPException(status_code=404, detail="Procedure type not found")

    start = snap_to_quarter(payload.starts_at)
    cp = CaseProcedure(
        episode_id=episode.id or 0,
        procedure_type_id=procedure_type.id or 0,
        status="planned",
        scheduled_start=start,
    )
    session.add(cp)
    session.flush()
    blocks = create_schedule_blocks(
        session,
        case_procedure=cp,
        procedure_type=procedure_type,
        room_name=payload.room_name,
        starts_at=start,
        assigned_staff_member_id=payload.assigned_staff_member_id,
    )
    session.commit()
    session.refresh(cp)
    event = write_audit(session, payload.actor_name, "scheduler_chain_generated", "case_procedure", cp.id or 0, f"Generated {procedure_type.name} chain for {episode.episode_ref}")
    return {"ok": True, "case_procedure": cp, "blocks": blocks, "audit_event": event, "conflicts": detect_conflicts(session)}


@router.post("/chains/{case_procedure_id}/move")
def move_chain(case_procedure_id: int, payload: MoveChainPayload, session: Session = Depends(get_session)):
    cp = session.get(CaseProcedure, case_procedure_id)
    if not cp:
        raise HTTPException(status_code=404, detail="Case procedure not found")
    blocks = block_chain(session, case_procedure_id)
    if not blocks:
        raise HTTPException(status_code=404, detail="No schedule blocks found for case procedure")

    new_start = snap_to_quarter(payload.starts_at)
    old_start = blocks[0].starts_at
    delta = new_start - old_start
    for block in blocks:
        block.starts_at = block.starts_at + delta
        block.ends_at = block.ends_at + delta
        session.add(block)
    cp.scheduled_start = new_start
    session.add(cp)
    session.commit()
    event = write_audit(session, payload.actor_name, "scheduler_chain_moved", "case_procedure", cp.id or 0, f"Moved chain by {delta}")
    result = serialise_chain(session, case_procedure_id)
    result.update({"ok": True, "audit_event": event})
    return result


@router.post("/chains/{case_procedure_id}/delay")
def delay_chain(case_procedure_id: int, payload: DelayChainPayload, session: Session = Depends(get_session)):
    cp = session.get(CaseProcedure, case_procedure_id)
    if not cp:
        raise HTTPException(status_code=404, detail="Case procedure not found")
    blocks = block_chain(session, case_procedure_id)
    if not blocks:
        raise HTTPException(status_code=404, detail="No schedule blocks found for case procedure")

    delta = timedelta(minutes=payload.minutes)
    for block in blocks:
        block.starts_at = block.starts_at + delta
        block.ends_at = block.ends_at + delta
        session.add(block)
    if cp.scheduled_start:
        cp.scheduled_start = cp.scheduled_start + delta
        session.add(cp)
    session.commit()
    event = write_audit(session, payload.actor_name, "scheduler_chain_delayed", "case_procedure", cp.id or 0, f"Delayed chain by {payload.minutes} minutes")
    result = serialise_chain(session, case_procedure_id)
    result.update({"ok": True, "audit_event": event})
    return result


@router.get("/chains/{case_procedure_id}")
def get_chain(case_procedure_id: int, session: Session = Depends(get_session)):
    return serialise_chain(session, case_procedure_id)


@router.get("/status")
def scheduler_status(session: Session = Depends(get_session)):
    blocks = session.exec(select(ScheduleBlock).order_by(ScheduleBlock.starts_at)).all()
    procedures = session.exec(select(CaseProcedure)).all()
    conflicts = detect_conflicts(session)
    active_blocks = [block for block in blocks if block.status != "done"]
    room_names = sorted({block.room_name for block in blocks if block.room_name})
    return {
        "generated_at": utc_now().isoformat(),
        "case_procedure_count": len(procedures),
        "schedule_block_count": len(blocks),
        "active_block_count": len(active_blocks),
        "rooms_in_schedule": room_names,
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "blocks": [row(block) for block in blocks[:160]],
    }
