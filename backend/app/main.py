from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine, get_session
from app.models import (
    Admission,
    AuditEvent,
    CaseProcedure,
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
    User,
    WorkItem,
)
from app.schemas import (
    LoginDemoRequest,
    MessageEntryCreate,
    MessageThreadCreate,
    ResultActionRequest,
    ScheduleGenerateRequest,
    WorkItemAssign,
    WorkItemCreate,
    WorkItemStatusUpdate,
)
from app.seed import seed_data

app = FastAPI(title="LucyWorks OS API", version="0.3.0")

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


@app.get("/")
def root() -> dict:
    return {"product": "LucyWorks OS", "status": "running"}


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "backend", "product": "LucyWorks OS"}


@app.get("/api/users")
def list_users(session: Session = Depends(get_session)):
    return session.exec(select(User)).all()


@app.get("/api/patients")
def list_patients(session: Session = Depends(get_session)):
    return session.exec(select(Patient).order_by(Patient.patient_name)).all()


@app.get("/api/episodes")
def list_episodes(session: Session = Depends(get_session)):
    return session.exec(select(Episode).order_by(Episode.created_at.desc())).all()


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
    items = session.exec(select(WorkItem)).all()
    results = session.exec(select(ResultReview)).all()
    handovers = session.exec(select(Handover)).all()
    room_states = session.exec(select(RoomState)).all()
    conflicts = _compute_conflicts(session)

    alerts = []

    for result in results:
        if result.status == "pending_review":
            alerts.append({"alert_type": "overdue_result", "severity": "high", "detail": f"Pending review for result {result.id}"})

    for item in items:
        if item.input_type == "discharge_blocker" and item.status != "done":
            alerts.append({"alert_type": "blocked_discharge", "severity": "high", "detail": item.title})

    for handover in handovers:
        if not handover.acknowledged:
            alerts.append({"alert_type": "unacknowledged_handover", "severity": "high", "detail": handover.note})

    for room_state in room_states:
        if room_state.state in {"blocked", "out_of_service"}:
            alerts.append({"alert_type": "room_unavailable", "severity": "medium", "detail": room_state.room_name})
        if room_state.state == "cleaning" and (room_state.cleaning_due_minutes or 0) > 15:
            alerts.append({"alert_type": "cleaning_overrun", "severity": "medium", "detail": room_state.room_name})

    for conflict in conflicts:
        alerts.append({"alert_type": conflict["type"], "severity": conflict["severity"], "detail": conflict["detail"]})

    if len([item for item in items if item.section_name == "ICU" and item.status != "done"]) >= 1:
        alerts.append({"alert_type": "icu_pressure", "severity": "high", "detail": "Active ICU pressure detected"})

    if len([item for item in items if item.section_name == "Imaging" and item.status != "done"]) >= 1:
        alerts.append({"alert_type": "imaging_backlog", "severity": "medium", "detail": "Imaging backlog detected"})

    return {
        "total_alerts": len(alerts),
        "high_alerts": len([a for a in alerts if a["severity"] == "high"]),
        "alerts": alerts,
    }


@app.get("/api/pulse")
def pulse(session: Session = Depends(get_session)):
    items = session.exec(select(WorkItem)).all()
    blocks = session.exec(select(ScheduleBlock)).all()
    handovers = session.exec(select(Handover)).all()
    results = session.exec(select(ResultReview)).all()
    room_states = session.exec(select(RoomState)).all()
    conflicts = _compute_conflicts(session)

    theatre_blocks = [b for b in blocks if b.room_name and "Theatre" in b.room_name]
    occupied_rooms = [r for r in room_states if r.state == "occupied"]
    pending_results = [r for r in results if r.status == "pending_review"]
    unacked_handovers = [h for h in handovers if not h.acknowledged]

    return {
        "case_pressure": len([i for i in items if i.status != "done"]),
        "resource_pressure": len(occupied_rooms) + len(conflicts),
        "staff_pressure": len([i for i in items if i.owner_role in {"nurse", "clinician"} and i.status != "done"]),
        "capacity_pressure": len([i for i in items if i.section_name in {"ICU", "Wards"} and i.status != "done"]),
        "execution_pressure": len(unacked_handovers) + len(pending_results),
        "theatre_blocks": len(theatre_blocks),
        "conflict_count": len(conflicts),
        "system_risk_level": "high" if len(conflicts) or len(pending_results) or len(unacked_handovers) else "normal",
    }


@app.get("/api/sections")
def list_sections(session: Session = Depends(get_session)):
    return session.exec(select(HospitalSection).order_by(HospitalSection.name)).all()


@app.get("/api/rooms")
def list_rooms(section_name: str | None = None, session: Session = Depends(get_session)):
    rooms = session.exec(select(Room).order_by(Room.section_name, Room.name)).all()
    if section_name:
        rooms = [room for room in rooms if room.section_name == section_name]
    return rooms


@app.post("/api/auth/login-demo")
def login_demo(payload: LoginDemoRequest, session: Session = Depends(get_session)):
    user = session.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user": user, "token": f"demo-token-{user.id}"}


@app.get("/api/work-items")
def list_work_items(role: str | None = None, session: Session = Depends(get_session)):
    items = session.exec(select(WorkItem).order_by(WorkItem.created_at.desc())).all()
    if role:
        items = [item for item in items if item.owner_role == role]
    return items


@app.post("/api/work-items")
def create_work_item(payload: WorkItemCreate, session: Session = Depends(get_session)):
    item = WorkItem(**payload.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    _log_event(session, "System", "created", "work_item", item.id or 0, f"Created work item: {item.title}")
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
    session.refresh(item)
    _log_event(session, payload.actor_name, "assigned", "work_item", item.id or 0, f"Assigned to role {payload.owner_role}")
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
    session.refresh(item)
    _log_event(session, payload.actor_name, "status_updated", "work_item", item.id or 0, f"Status changed to {payload.status}")
    return item


@app.post("/api/schedule/generate")
def generate_schedule(payload: ScheduleGenerateRequest, session: Session = Depends(get_session)):
    episode = session.exec(select(Episode).where(Episode.episode_ref == payload.episode_ref)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    procedure = session.get(ProcedureType, payload.procedure_type_id)
    if not procedure:
        raise HTTPException(status_code=404, detail="Procedure type not found")

    case_proc = CaseProcedure(
        episode_id=episode.id,
        procedure_type_id=procedure.id,
        scheduled_start=payload.start_time,
    )
    session.add(case_proc)
    session.commit()
    session.refresh(case_proc)

    blocks = []
    current = payload.start_time

    def add_block(name: str, minutes: int):
        nonlocal current
        block = ScheduleBlock(
            episode_id=episode.id,
            case_procedure_id=case_proc.id,
            block_type=name,
            room_name=payload.room_name,
            owner_role=procedure.required_role,
            starts_at=current,
            ends_at=current + timedelta(minutes=minutes),
        )
        current = block.ends_at
        blocks.append(block)

    add_block("prep", procedure.prep_min)
    add_block("anaesthesia", procedure.anaesthesia_min)
    add_block("procedure", procedure.default_duration_min)
    add_block("recovery", procedure.recovery_min)
    add_block("cleaning", procedure.cleaning_min)

    for block in blocks:
        session.add(block)
    session.commit()

    episode.current_phase = "scheduled"
    episode.current_room_name = payload.room_name
    episode.current_section_name = procedure.department
    session.add(episode)
    session.commit()

    _log_event(session, payload.actor_name, "schedule_generated", "case_procedure", case_proc.id or 0, f"Generated schedule chain for {payload.episode_ref}")
    return {"case_procedure": case_proc, "blocks": blocks}


@app.get("/api/conflicts")
def get_conflicts(session: Session = Depends(get_session)):
    return {"conflicts": _compute_conflicts(session)}


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
    _log_event(session, payload.actor_name, "result_actioned", "result_review", result.id or 0, f"Result set to {payload.status}")
    return result


@app.post("/api/messages/thread")
def create_thread(payload: MessageThreadCreate, session: Session = Depends(get_session)):
    episode_id = None
    if payload.episode_ref:
        episode = session.exec(select(Episode).where(Episode.episode_ref == payload.episode_ref)).first()
        if not episode:
            raise HTTPException(status_code=404, detail="Episode not found")
        episode_id = episode.id

    thread = MessageThread(
        episode_id=episode_id,
        source_type=payload.source_type,
        subject=payload.subject,
        owner_role=payload.owner_role,
        owner_user_id=payload.owner_user_id,
    )
    session.add(thread)
    session.commit()
    session.refresh(thread)
    _log_event(session, "System", "thread_created", "message_thread", thread.id or 0, f"Created thread: {thread.subject}")
    return thread


@app.post("/api/messages/{thread_id}")
def add_message(thread_id: int, payload: MessageEntryCreate, session: Session = Depends(get_session)):
    thread = session.get(MessageThread, thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    entry = MessageEntry(
        thread_id=thread_id,
        sender_name=payload.sender_name,
        direction=payload.direction,
        body=payload.body,
        material_decision_flag=payload.material_decision_flag,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    _log_event(session, payload.actor_name, "message_added", "message_thread", thread_id, f"Added {payload.direction} message")
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
    _log_event(session, "System", "room_state_changed", "room_state", room_state.id or 0, f"Room state changed to {state}")
    return room_state


@app.get("/api/audit")
def list_audit(session: Session = Depends(get_session)):
    return session.exec(select(AuditEvent).order_by(AuditEvent.created_at.desc())).all()


@app.get("/api/director-board")
def director_board(session: Session = Depends(get_session)):
    items = session.exec(select(WorkItem).order_by(WorkItem.created_at.desc())).all()

    def count_where(fn):
        return len([item for item in items if fn(item)])

    cards = [
        {"key": "red_alerts", "label": "Red alerts", "value": count_where(lambda i: i.urgency == "red"), "tone": "critical"},
        {"key": "unowned_work", "label": "Unowned work", "value": count_where(lambda i: i.owner_user_id is None), "tone": "warning"},
        {"key": "theatre_risk", "label": "Theatre risk", "value": count_where(lambda i: i.section_name == "Theatres" and i.urgency in {"amber", "red"}), "tone": "critical"},
        {"key": "ward_pressure", "label": "Ward pressure", "value": count_where(lambda i: i.section_name == "Wards" and i.status != "done"), "tone": "warning"},
        {"key": "consult_pressure", "label": "Consult pressure", "value": count_where(lambda i: i.section_name == "Consults" and i.status != "done"), "tone": "warning"},
        {"key": "imaging_reviews", "label": "Imaging reviews", "value": count_where(lambda i: i.section_name == "Imaging" and i.status != "done"), "tone": "info"},
        {"key": "discharge_blockers", "label": "Discharge blockers", "value": count_where(lambda i: i.input_type == "discharge_blocker" and i.status != "done"), "tone": "warning"},
        {"key": "new_inputs", "label": "New inputs", "value": count_where(lambda i: i.status == "new"), "tone": "neutral"},
    ]

    section_names = sorted({item.section_name for item in items if item.section_name})
    section_pressure = []
    for name in section_names:
        section_items = [item for item in items if item.section_name == name]
        section_pressure.append({
            "section_name": name,
            "live": len([item for item in section_items if item.status != "done"]),
            "red": len([item for item in section_items if item.urgency == "red"]),
            "unowned": len([item for item in section_items if item.owner_user_id is None]),
        })

    priority_items = [item for item in items if item.urgency == "red" or item.status == "new"][:10]
    return {"cards": cards, "section_pressure": section_pressure, "priority_items": priority_items}


@app.get("/api/consult-board")
def consult_board(session: Session = Depends(get_session)):
    items = session.exec(select(WorkItem).order_by(WorkItem.created_at.desc())).all()
    consult_items = [item for item in items if item.section_name == "Consults"]
    room_states = session.exec(select(RoomState).where(RoomState.department == "Consults")).all()

    def count_where(fn):
        return len([item for item in consult_items if fn(item)])

    cards = [
        {"key": "consult_live", "label": "Consult live", "value": count_where(lambda i: i.status != "done"), "tone": "warning"},
        {"key": "notes_incomplete", "label": "Notes incomplete", "value": count_where(lambda i: i.category == "documentation" and i.status != "done"), "tone": "warning"},
        {"key": "owner_updates", "label": "Owner updates", "value": count_where(lambda i: i.category == "owner_comms" and i.status != "done"), "tone": "info"},
        {"key": "follow_up", "label": "Follow-up pending", "value": count_where(lambda i: i.category == "follow_up" and i.status != "done"), "tone": "critical"},
    ]

    rooms = sorted({item.room_name for item in consult_items if item.room_name})
    room_groups = []
    for room_name in rooms:
        room_items = [item for item in consult_items if item.room_name == room_name]
        room_state = next((state for state in room_states if state.room_name == room_name), None)
        room_groups.append({
            "room_name": room_name,
            "state": room_state.state if room_state else "unknown",
            "current_episode_ref": room_state.current_episode_ref if room_state else None,
            "next_episode_ref": room_state.next_episode_ref if room_state else None,
            "live": len([item for item in room_items if item.status != "done"]),
            "red": len([item for item in room_items if item.urgency == "red"]),
            "items": room_items,
        })
    return {"cards": cards, "room_groups": room_groups}


@app.get("/api/ward-board")
def ward_board(session: Session = Depends(get_session)):
    items = session.exec(select(WorkItem).order_by(WorkItem.created_at.desc())).all()
    ward_items = [item for item in items if item.section_name in {"Wards", "ICU"}]

    def count_where(fn):
        return len([item for item in ward_items if fn(item)])

    cards = [
        {"key": "icu_red", "label": "ICU red", "value": count_where(lambda i: i.section_name == "ICU" and i.urgency == "red"), "tone": "critical"},
        {"key": "ward_live", "label": "Ward live", "value": count_where(lambda i: i.section_name == "Wards" and i.status != "done"), "tone": "warning"},
        {"key": "discharge_blockers", "label": "Discharge blockers", "value": count_where(lambda i: i.input_type == "discharge_blocker" and i.status != "done"), "tone": "warning"},
        {"key": "unowned_inpatient", "label": "Unowned inpatient", "value": count_where(lambda i: i.owner_user_id is None), "tone": "warning"},
        {"key": "clinician_review", "label": "Clinician review", "value": count_where(lambda i: i.owner_role == "clinician" and i.status != "done"), "tone": "info"},
        {"key": "nurse_queue", "label": "Nurse queue", "value": count_where(lambda i: i.owner_role == "nurse" and i.status != "done"), "tone": "stable"},
    ]
    rooms = sorted({item.room_name for item in ward_items if item.room_name})
    room_groups = []
    for room_name in rooms:
        room_items = [item for item in ward_items if item.room_name == room_name]
        room_groups.append({
            "room_name": room_name,
            "section_name": room_items[0].section_name if room_items else None,
            "live": len([item for item in room_items if item.status != "done"]),
            "red": len([item for item in room_items if item.urgency == "red"]),
            "items": room_items,
        })
    return {"cards": cards, "room_groups": room_groups}


@app.get("/api/theatre-board")
def theatre_board(session: Session = Depends(get_session)):
    items = session.exec(select(WorkItem).order_by(WorkItem.created_at.desc())).all()
    theatre_items = [item for item in items if item.section_name in {"Theatres", "Recovery"}]

    def count_where(fn):
        return len([item for item in theatre_items if fn(item)])

    cards = [
        {"key": "theatre_red", "label": "Theatre red", "value": count_where(lambda i: i.section_name == "Theatres" and i.urgency == "red"), "tone": "critical"},
        {"key": "recovery_live", "label": "Recovery live", "value": count_where(lambda i: i.section_name == "Recovery" and i.status != "done"), "tone": "warning"},
        {"key": "prep_blockers", "label": "Prep blockers", "value": count_where(lambda i: i.category == "prep" and i.status != "done"), "tone": "warning"},
        {"key": "handoff_gaps", "label": "Handoff gaps", "value": count_where(lambda i: i.category == "handoff" and i.status != "done"), "tone": "info"},
        {"key": "ops_risk", "label": "Ops risk", "value": count_where(lambda i: i.owner_role == "ops_manager" and i.status != "done"), "tone": "critical"},
        {"key": "nurse_actions", "label": "Nurse actions", "value": count_where(lambda i: i.owner_role == "nurse" and i.status != "done"), "tone": "stable"},
    ]
    rooms = sorted({item.room_name for item in theatre_items if item.room_name})
    room_groups = []
    for room_name in rooms:
        room_items = [item for item in theatre_items if item.room_name == room_name]
        room_groups.append({
            "room_name": room_name,
            "section_name": room_items[0].section_name if room_items else None,
            "live": len([item for item in room_items if item.status != "done"]),
            "red": len([item for item in room_items if item.urgency == "red"]),
            "items": room_items,
        })
    return {"cards": cards, "room_groups": room_groups}


def _compute_conflicts(session: Session):
    blocks = session.exec(select(ScheduleBlock).order_by(ScheduleBlock.starts_at)).all()
    room_states = session.exec(select(RoomState)).all()
    results = session.exec(select(ResultReview)).all()
    handovers = session.exec(select(Handover)).all()

    conflicts = []

    for first in blocks:
        for second in blocks:
            if first.id >= second.id:
                continue
            overlap = not (first.ends_at <= second.starts_at or second.ends_at <= first.starts_at)
            if overlap and first.room_name == second.room_name:
                conflicts.append({"type": "room_conflict", "severity": "high", "detail": f"{first.room_name} overlap between blocks {first.id} and {second.id}"})
            if overlap and first.owner_role and second.owner_role and first.owner_role == second.owner_role:
                conflicts.append({"type": "staff_conflict", "severity": "medium", "detail": f"{first.owner_role} overlap between blocks {first.id} and {second.id}"})

    for room_state in room_states:
        if room_state.state == "cleaning" and room_state.next_episode_ref:
            conflicts.append({"type": "cleaning_chain_conflict", "severity": "medium", "detail": f"{room_state.room_name} still cleaning before next episode {room_state.next_episode_ref}"})

    for result in results:
        if result.status == "pending_review":
            conflicts.append({"type": "result_sla_conflict", "severity": "medium", "detail": f"Result {result.id} still pending review"})

    for handover in handovers:
        if not handover.acknowledged:
            conflicts.append({"type": "handover_conflict", "severity": "high", "detail": handover.note})

    return conflicts


def _log_event(session: Session, actor_name: str, action: str, entity_type: str, entity_id: int, summary: str):
    session.add(AuditEvent(actor_name=actor_name, action=action, entity_type=entity_type, entity_id=entity_id, summary=summary))
    session.commit()
