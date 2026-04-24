from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine, get_session
from app.models import (
    Admission,
    AuditEvent,
    CaseProcedure,
    ConflictAction,
    Episode,
    Handover,
    HospitalSection,
    MessageEntry,
    MessageThread,
    Patient,
    ProcedureType,
    ResultReview,
    Room,
    RoomState,
    ScheduleBlock,
    Shift,
    StaffMember,
    User,
    WorkItem,
)
from app.schemas import (
    LoginDemoRequest,
    MessageEntryCreate,
    MessageThreadCreate,
    ResultActionRequest,
    ScheduleGenerateRequest,
    ScheduleShiftRequest,
    StaffAllocateRequest,
    WorkItemAssign,
    WorkItemCreate,
    WorkItemStatusUpdate,
)
from app.seed import seed_data

app = FastAPI(title="LucyWorks OS API", version="0.5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()
    with Session(engine) as session:
        seed_data(session)


def log_event(session: Session, actor_name: str, action: str, entity_type: str, entity_id: int, summary: str) -> None:
    session.add(AuditEvent(actor_name=actor_name, action=action, entity_type=entity_type, entity_id=entity_id, summary=summary))
    session.commit()


def overlap(a_start, a_end, b_start, b_end) -> bool:
    return not (a_end <= b_start or b_end <= a_start)


def compute_conflicts(session: Session):
    blocks = session.exec(select(ScheduleBlock).order_by(ScheduleBlock.starts_at)).all()
    room_states = session.exec(select(RoomState)).all()
    results = session.exec(select(ResultReview)).all()
    handovers = session.exec(select(Handover)).all()
    conflicts = []

    for i, first in enumerate(blocks):
        for second in blocks[i + 1:]:
            if second.starts_at >= first.ends_at and first.room_name != second.room_name and first.owner_role != second.owner_role:
                continue
            if overlap(first.starts_at, first.ends_at, second.starts_at, second.ends_at):
                if first.room_name and first.room_name == second.room_name:
                    conflicts.append({"type": "room_conflict", "severity": "high", "detail": f"{first.room_name} overlap: block {first.id} and block {second.id}", "episode_ids": [first.episode_id, second.episode_id]})
                if first.owner_role and first.owner_role == second.owner_role:
                    conflicts.append({"type": "staff_role_conflict", "severity": "medium", "detail": f"{first.owner_role} overlap: block {first.id} and block {second.id}", "episode_ids": [first.episode_id, second.episode_id]})

    for room_state in room_states:
        if room_state.state == "cleaning" and room_state.next_episode_ref:
            conflicts.append({"type": "cleaning_chain_conflict", "severity": "medium", "detail": f"{room_state.room_name} cleaning before {room_state.next_episode_ref}", "episode_ids": []})

    for result in results:
        if result.status == "pending_review":
            conflicts.append({"type": "result_review_conflict", "severity": "medium", "detail": f"Result {result.id} pending review", "episode_ids": [result.episode_id]})

    for handover in handovers:
        if not handover.acknowledged:
            conflicts.append({"type": "handover_conflict", "severity": "high", "detail": handover.note, "episode_ids": [handover.episode_id]})

    return conflicts


def derive_alerts(session: Session):
    items = session.exec(select(WorkItem)).all()
    alerts = []
    alerts.extend(compute_conflicts(session))
    for item in items:
        if item.input_type == "discharge_blocker" and item.status != "done":
            alerts.append({"type": "blocked_discharge", "severity": "high", "detail": item.title, "episode_ids": []})
    if any(i.section_name == "ICU" and i.status != "done" for i in items):
        alerts.append({"type": "icu_pressure", "severity": "high", "detail": "Active ICU pressure detected", "episode_ids": []})
    return alerts


@app.get("/")
def root():
    return {"product": "LucyWorks OS", "status": "running"}


@app.get("/api/health")
def health():
    return {"ok": True, "service": "backend", "product": "LucyWorks OS"}


@app.get("/api/users")
def list_users(session: Session = Depends(get_session)):
    return session.exec(select(User)).all()


@app.get("/api/staff")
def list_staff(session: Session = Depends(get_session)):
    return session.exec(select(StaffMember).order_by(StaffMember.role, StaffMember.name)).all()


@app.get("/api/shifts")
def list_shifts(session: Session = Depends(get_session)):
    return session.exec(select(Shift).order_by(Shift.starts_at)).all()


@app.get("/api/patients")
def list_patients(session: Session = Depends(get_session)):
    return session.exec(select(Patient).order_by(Patient.patient_name)).all()


@app.get("/api/episodes")
def list_episodes(session: Session = Depends(get_session)):
    return session.exec(select(Episode).order_by(Episode.created_at.desc())).all()


@app.get("/api/episode-command/{episode_ref}")
def episode_command(episode_ref: str, session: Session = Depends(get_session)):
    episode = session.exec(select(Episode).where(Episode.episode_ref == episode_ref)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    return {
        "episode": episode,
        "patient": session.get(Patient, episode.patient_id),
        "admissions": session.exec(select(Admission).where(Admission.episode_id == episode.id)).all(),
        "handovers": session.exec(select(Handover).where(Handover.episode_id == episode.id)).all(),
        "results": session.exec(select(ResultReview).where(ResultReview.episode_id == episode.id)).all(),
        "schedule_blocks": session.exec(select(ScheduleBlock).where(ScheduleBlock.episode_id == episode.id).order_by(ScheduleBlock.starts_at)).all(),
        "message_threads": session.exec(select(MessageThread).where(MessageThread.episode_id == episode.id).order_by(MessageThread.created_at.desc())).all(),
        "work_items": session.exec(select(WorkItem).where(WorkItem.linked_episode_ref == episode_ref).order_by(WorkItem.created_at.desc())).all(),
        "room_state": session.exec(select(RoomState).where(RoomState.room_name == episode.current_room_name)).first() if episode.current_room_name else None,
        "conflicts": [c for c in compute_conflicts(session) if episode.id in c.get("episode_ids", [])],
    }


@app.get("/api/admissions")
def list_admissions(session: Session = Depends(get_session)):
    return session.exec(select(Admission).order_by(Admission.admitted_at.desc())).all()


@app.get("/api/handovers")
def list_handovers(session: Session = Depends(get_session)):
    return session.exec(select(Handover).order_by(Handover.created_at.desc())).all()


@app.get("/api/results")
def list_results(session: Session = Depends(get_session)):
    return session.exec(select(ResultReview).order_by(ResultReview.id.desc())).all()


@app.get("/api/room-states")
def list_room_states(session: Session = Depends(get_session)):
    return session.exec(select(RoomState).order_by(RoomState.department, RoomState.room_name)).all()


@app.get("/api/procedure-types")
def list_procedure_types(session: Session = Depends(get_session)):
    return session.exec(select(ProcedureType).order_by(ProcedureType.department, ProcedureType.name)).all()


@app.get("/api/case-procedures")
def list_case_procedures(session: Session = Depends(get_session)):
    return session.exec(select(CaseProcedure).order_by(CaseProcedure.id.desc())).all()


@app.get("/api/schedule-blocks")
def list_schedule_blocks(session: Session = Depends(get_session)):
    return session.exec(select(ScheduleBlock).order_by(ScheduleBlock.starts_at)).all()


@app.get("/api/message-threads")
def list_message_threads(session: Session = Depends(get_session)):
    return session.exec(select(MessageThread).order_by(MessageThread.created_at.desc())).all()


@app.get("/api/message-threads/{thread_id}/entries")
def list_message_entries(thread_id: int, session: Session = Depends(get_session)):
    return session.exec(select(MessageEntry).where(MessageEntry.thread_id == thread_id).order_by(MessageEntry.created_at)).all()


@app.get("/api/alerts")
def list_alerts(session: Session = Depends(get_session)):
    alerts = derive_alerts(session)
    return {"total_alerts": len(alerts), "high_alerts": len([a for a in alerts if a["severity"] == "high"]), "alerts": alerts}


@app.get("/api/pulse")
def pulse(session: Session = Depends(get_session)):
    items = session.exec(select(WorkItem)).all()
    room_states = session.exec(select(RoomState)).all()
    conflicts = compute_conflicts(session)
    pending_results = session.exec(select(ResultReview).where(ResultReview.status == "pending_review")).all()
    unacked_handovers = session.exec(select(Handover).where(Handover.acknowledged == False)).all()
    return {
        "case_pressure": len([i for i in items if i.status != "done"]),
        "resource_pressure": len([r for r in room_states if r.state == "occupied"]) + len(conflicts),
        "staff_pressure": len([i for i in items if i.owner_role in {"nurse", "clinician"} and i.status != "done"]),
        "capacity_pressure": len([i for i in items if i.section_name in {"ICU", "Wards"} and i.status != "done"]),
        "execution_pressure": len(unacked_handovers) + len(pending_results),
        "conflict_count": len(conflicts),
        "system_risk_level": "high" if conflicts or pending_results or unacked_handovers else "normal",
    }


@app.get("/api/sections")
def list_sections(session: Session = Depends(get_session)):
    return session.exec(select(HospitalSection).order_by(HospitalSection.name)).all()


@app.get("/api/rooms")
def list_rooms(section_name: str | None = None, session: Session = Depends(get_session)):
    rooms = session.exec(select(Room).order_by(Room.section_name, Room.name)).all()
    return [room for room in rooms if room.section_name == section_name] if section_name else rooms


@app.post("/api/auth/login-demo")
def login_demo(payload: LoginDemoRequest, session: Session = Depends(get_session)):
    user = session.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user": user, "token": f"demo-token-{user.id}"}


@app.get("/api/work-items")
def list_work_items(role: str | None = None, session: Session = Depends(get_session)):
    items = session.exec(select(WorkItem).order_by(WorkItem.created_at.desc())).all()
    return [item for item in items if item.owner_role == role] if role else items


@app.post("/api/work-items")
def create_work_item(payload: WorkItemCreate, session: Session = Depends(get_session)):
    item = WorkItem(**payload.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    log_event(session, "System", "created", "work_item", item.id or 0, f"Created work item: {item.title}")
    return item


@app.post("/api/work-items/{item_id}/assign")
def assign_work_item(item_id: int, payload: WorkItemAssign, session: Session = Depends(get_session)):
    item = session.get(WorkItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Work item not found")
    item.owner_role = payload.owner_role
    item.owner_user_id = payload.owner_user_id
    session.add(item)
    session.commit()
    log_event(session, payload.actor_name, "assigned", "work_item", item.id or 0, f"Assigned to role {payload.owner_role}")
    return item


@app.post("/api/work-items/{item_id}/status")
def update_work_item_status(item_id: int, payload: WorkItemStatusUpdate, session: Session = Depends(get_session)):
    item = session.get(WorkItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Work item not found")
    item.status = payload.status
    item.updated_at = datetime.now(timezone.utc)
    session.add(item)
    session.commit()
    log_event(session, payload.actor_name, "status_updated", "work_item", item.id or 0, f"Status changed to {payload.status}")
    return item


@app.post("/api/schedule/generate")
def generate_schedule(payload: ScheduleGenerateRequest, session: Session = Depends(get_session)):
    episode = session.exec(select(Episode).where(Episode.episode_ref == payload.episode_ref)).first()
    procedure = session.get(ProcedureType, payload.procedure_type_id)
    if not episode or not procedure:
        raise HTTPException(status_code=404, detail="Episode or procedure not found")

    # remove existing planned blocks for a cleaner demo flow
    case_proc = CaseProcedure(episode_id=episode.id, procedure_type_id=procedure.id, scheduled_start=payload.start_time)
    session.add(case_proc)
    session.commit()
    session.refresh(case_proc)

    blocks = []
    current = payload.start_time
    for name, minutes in [("prep", procedure.prep_min), ("anaesthesia", procedure.anaesthesia_min), ("procedure", procedure.default_duration_min), ("recovery", procedure.recovery_min), ("cleaning", procedure.cleaning_min)]:
        block = ScheduleBlock(episode_id=episode.id, case_procedure_id=case_proc.id, block_type=name, room_name=payload.room_name, owner_role=procedure.required_role, starts_at=current, ends_at=current + timedelta(minutes=minutes))
        current = block.ends_at
        session.add(block)
        blocks.append(block)
    episode.current_phase = "scheduled"
    episode.current_room_name = payload.room_name
    episode.current_section_name = procedure.department
    session.add(episode)
    session.commit()
    log_event(session, payload.actor_name, "schedule_generated", "case_procedure", case_proc.id or 0, f"Generated schedule for {payload.episode_ref}")
    return {"case_procedure": case_proc, "blocks": blocks}


@app.post("/api/schedule/block/{block_id}/shift")
def shift_block(block_id: int, payload: ScheduleShiftRequest, session: Session = Depends(get_session)):
    block = session.get(ScheduleBlock, block_id)
    if not block:
        raise HTTPException(status_code=404, detail="Block not found")
    delta = timedelta(minutes=payload.minutes)
    blocks = session.exec(select(ScheduleBlock).where(ScheduleBlock.case_procedure_id == block.case_procedure_id).order_by(ScheduleBlock.starts_at)).all()
    found = False
    for target in blocks:
        if target.id == block.id:
            found = True
        if found:
            target.starts_at += delta
            target.ends_at += delta
            session.add(target)
    session.commit()
    log_event(session, payload.actor_name, "schedule_shifted", "schedule_block", block_id, f"Shifted chain by {payload.minutes} minutes")
    return {"status": "shifted", "block_id": block_id, "minutes": payload.minutes}


@app.post("/api/staff/allocate")
def allocate_staff(payload: StaffAllocateRequest, session: Session = Depends(get_session)):
    block = session.get(ScheduleBlock, payload.schedule_block_id)
    staff = session.get(StaffMember, payload.staff_member_id)
    if not block or not staff:
        raise HTTPException(status_code=404, detail="Invalid block or staff")
    shifts = session.exec(select(Shift).where(Shift.staff_member_id == staff.id)).all()
    if not any(s.starts_at <= block.starts_at and s.ends_at >= block.ends_at for s in shifts):
        return {"status": "conflict", "detail": "Staff not available"}
    block.owner_role = staff.role
    session.add(block)
    session.commit()
    log_event(session, payload.actor_name, "staff_allocated", "schedule_block", block.id or 0, f"Allocated {staff.name}")
    return {"status": "allocated", "staff": staff.name}


@app.get("/api/conflicts")
def get_conflicts(session: Session = Depends(get_session)):
    return {"conflicts": compute_conflicts(session)}


@app.post("/api/conflicts/to-work")
def conflict_to_work(conflict_type: str, severity: str, detail: str, session: Session = Depends(get_session)):
    item = WorkItem(title=f"Resolve {conflict_type}", input_type="conflict", source="conflict_engine", category="resolution", description=detail, urgency="red" if severity == "high" else "amber", owner_role="ops_manager", status="new")
    session.add(item)
    session.commit()
    session.refresh(item)
    action = ConflictAction(conflict_type=conflict_type, severity=severity, detail=detail, linked_work_item_id=item.id)
    session.add(action)
    session.commit()
    log_event(session, "System", "conflict_to_work", "work_item", item.id or 0, f"Created work from {conflict_type}")
    return {"work_item": item, "conflict_action": action}


@app.post("/api/results/{result_id}/action")
def action_result(result_id: int, payload: ResultActionRequest, session: Session = Depends(get_session)):
    result = session.get(ResultReview, result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    result.status = payload.status
    result.required_action = payload.required_action
    result.reviewed_at = datetime.now(timezone.utc)
    session.add(result)
    session.commit()
    log_event(session, payload.actor_name, "result_actioned", "result_review", result.id or 0, f"Result set to {payload.status}")
    return result


@app.post("/api/messages/thread")
def create_thread(payload: MessageThreadCreate, session: Session = Depends(get_session)):
    episode_id = None
    if payload.episode_ref:
        episode = session.exec(select(Episode).where(Episode.episode_ref == payload.episode_ref)).first()
        if not episode:
            raise HTTPException(status_code=404, detail="Episode not found")
        episode_id = episode.id
    thread = MessageThread(episode_id=episode_id, source_type=payload.source_type, subject=payload.subject, owner_role=payload.owner_role, owner_user_id=payload.owner_user_id)
    session.add(thread)
    session.commit()
    session.refresh(thread)
    log_event(session, "System", "thread_created", "message_thread", thread.id or 0, f"Created thread: {thread.subject}")
    return thread


@app.post("/api/messages/{thread_id}")
def add_message(thread_id: int, payload: MessageEntryCreate, session: Session = Depends(get_session)):
    thread = session.get(MessageThread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    entry = MessageEntry(thread_id=thread_id, sender_name=payload.sender_name, direction=payload.direction, body=payload.body, material_decision_flag=payload.material_decision_flag)
    session.add(entry)
    session.commit()
    session.refresh(entry)
    log_event(session, payload.actor_name, "message_added", "message_thread", thread_id, f"Added {payload.direction} message")
    return entry


@app.post("/api/room-states/{room_state_id}/set")
def set_room_state(room_state_id: int, state: str, session: Session = Depends(get_session)):
    room_state = session.get(RoomState, room_state_id)
    if not room_state:
        raise HTTPException(status_code=404, detail="Room state not found")
    room_state.state = state
    if state == "cleaning" and not room_state.cleaning_due_minutes:
        room_state.cleaning_due_minutes = 20
    if state == "available":
        room_state.current_episode_ref = None
        room_state.next_episode_ref = None
        room_state.cleaning_due_minutes = None
    session.add(room_state)
    session.commit()
    log_event(session, "System", "room_state_changed", "room_state", room_state.id or 0, f"Room state changed to {state}")
    return room_state


@app.get("/api/audit")
def list_audit(session: Session = Depends(get_session)):
    return session.exec(select(AuditEvent).order_by(AuditEvent.created_at.desc())).all()
