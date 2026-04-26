from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine, get_session
from app.models import (
    Admission, AuditEvent, CaseProcedure, ConflictAction, Episode, Handover,
    HospitalSection, MessageEntry, MessageThread, Patient, ProcedureType,
    ResultReview, Room, RoomState, ScheduleBlock, Shift, StaffMember, User, WorkItem,
)
from app.schemas import (
    LoginDemoRequest, MessageEntryCreate, MessageThreadCreate, ResultActionRequest,
    ScheduleGenerateRequest, ScheduleShiftRequest, StaffAllocateRequest,
    WorkItemAssign, WorkItemCreate, WorkItemStatusUpdate,
)
from app.seed import seed_data

app = FastAPI(title="LucyWorks OS API", version="0.8.0-fixed")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    create_db_and_tables()
    with Session(engine) as session:
        seed_data(session)

def log(session: Session, actor: str, action: str, entity: str, entity_id: int, summary: str):
    session.add(AuditEvent(actor_name=actor, action=action, entity_type=entity, entity_id=entity_id, summary=summary))
    session.commit()

def overlaps(a_start, a_end, b_start, b_end):
    return not (a_end <= b_start or b_end <= a_start)

def on_shift(session: Session, staff_id: int, starts_at: datetime, ends_at: datetime):
    shifts = session.exec(select(Shift).where(Shift.staff_member_id == staff_id)).all()
    return any(s.starts_at <= starts_at and s.ends_at >= ends_at and s.status in {"active", "planned"} for s in shifts)

def compute_conflicts(session: Session):
    blocks = session.exec(select(ScheduleBlock).order_by(ScheduleBlock.starts_at)).all()
    out = []
    for i, a in enumerate(blocks):
        for b in blocks[i + 1:]:
            if not overlaps(a.starts_at, a.ends_at, b.starts_at, b.ends_at):
                continue
            if a.room_name and a.room_name == b.room_name:
                out.append({"type": "room_conflict", "severity": "high", "detail": f"{a.room_name} overlap: block {a.id} and block {b.id}", "episode_ids": [a.episode_id, b.episode_id]})
            if a.assigned_staff_member_id and a.assigned_staff_member_id == b.assigned_staff_member_id:
                out.append({"type": "staff_conflict", "severity": "high", "detail": f"Staff {a.assigned_staff_member_id} overlap: block {a.id} and block {b.id}", "episode_ids": [a.episode_id, b.episode_id]})
            elif a.owner_role and a.owner_role == b.owner_role:
                out.append({"type": "staff_role_conflict", "severity": "medium", "detail": f"Role {a.owner_role} overlap: block {a.id} and block {b.id}", "episode_ids": [a.episode_id, b.episode_id]})
    for r in session.exec(select(RoomState)).all():
        if r.state == "cleaning" and r.next_episode_ref:
            out.append({"type": "cleaning_chain_conflict", "severity": "medium", "detail": f"{r.room_name} cleaning before {r.next_episode_ref}", "episode_ids": []})
    for r in session.exec(select(ResultReview)).all():
        if r.status == "pending_review":
            out.append({"type": "result_review_conflict", "severity": "medium", "detail": f"Result {r.id} pending review", "episode_ids": [r.episode_id]})
    for h in session.exec(select(Handover)).all():
        if not h.acknowledged:
            out.append({"type": "handover_conflict", "severity": "high", "detail": h.note, "episode_ids": [h.episode_id]})
    return out

def board_cards(items):
    return [
        {"key": "red_alerts", "label": "Red alerts", "value": len([i for i in items if i.urgency == "red"]), "tone": "critical"},
        {"key": "unowned_work", "label": "Unowned work", "value": len([i for i in items if i.owner_user_id is None]), "tone": "warning"},
        {"key": "new_inputs", "label": "New inputs", "value": len([i for i in items if i.status == "new"]), "tone": "neutral"},
        {"key": "live_work", "label": "Live work", "value": len([i for i in items if i.status != "done"]), "tone": "info"},
    ]

def room_groups(items):
    out = []
    for room in sorted({i.room_name for i in items if i.room_name}):
        rows = [i for i in items if i.room_name == room]
        out.append({"room_name": room, "section_name": rows[0].section_name, "live": len([i for i in rows if i.status != "done"]), "red": len([i for i in rows if i.urgency == "red"]), "items": rows})
    return out

@app.get("/")
def root(): return {"product": "LucyWorks OS", "status": "running", "entrypoint": "main_fixed"}
@app.get("/api/health")
def health(): return {"ok": True, "service": "backend", "product": "LucyWorks OS", "entrypoint": "main_fixed"}
@app.get("/api/users")
def users(session: Session = Depends(get_session)): return session.exec(select(User)).all()
@app.get("/api/staff")
def staff(session: Session = Depends(get_session)): return session.exec(select(StaffMember).order_by(StaffMember.role, StaffMember.name)).all()
@app.get("/api/shifts")
def shifts(session: Session = Depends(get_session)): return session.exec(select(Shift).order_by(Shift.starts_at)).all()
@app.get("/api/patients")
def patients(session: Session = Depends(get_session)): return session.exec(select(Patient).order_by(Patient.patient_name)).all()
@app.get("/api/episodes")
def episodes(session: Session = Depends(get_session)): return session.exec(select(Episode).order_by(Episode.created_at.desc())).all()
@app.get("/api/admissions")
def admissions(session: Session = Depends(get_session)): return session.exec(select(Admission).order_by(Admission.admitted_at.desc())).all()
@app.get("/api/handovers")
def handovers(session: Session = Depends(get_session)): return session.exec(select(Handover).order_by(Handover.created_at.desc())).all()
@app.get("/api/results")
def results(session: Session = Depends(get_session)): return session.exec(select(ResultReview).order_by(ResultReview.id.desc())).all()
@app.get("/api/room-states")
def room_states(session: Session = Depends(get_session)): return session.exec(select(RoomState).order_by(RoomState.department, RoomState.room_name)).all()
@app.get("/api/procedure-types")
def procedure_types(session: Session = Depends(get_session)): return session.exec(select(ProcedureType).order_by(ProcedureType.department, ProcedureType.name)).all()
@app.get("/api/case-procedures")
def case_procedures(session: Session = Depends(get_session)): return session.exec(select(CaseProcedure).order_by(CaseProcedure.id.desc())).all()
@app.get("/api/schedule-blocks")
def schedule_blocks(session: Session = Depends(get_session)): return session.exec(select(ScheduleBlock).order_by(ScheduleBlock.starts_at)).all()
@app.get("/api/message-threads")
def message_threads(session: Session = Depends(get_session)): return session.exec(select(MessageThread).order_by(MessageThread.created_at.desc())).all()
@app.get("/api/message-threads/{thread_id}/entries")
def message_entries(thread_id: int, session: Session = Depends(get_session)): return session.exec(select(MessageEntry).where(MessageEntry.thread_id == thread_id).order_by(MessageEntry.created_at)).all()
@app.get("/api/sections")
def sections(session: Session = Depends(get_session)): return session.exec(select(HospitalSection).order_by(HospitalSection.name)).all()
@app.get("/api/rooms")
def rooms(section_name: str | None = None, session: Session = Depends(get_session)):
    rows = session.exec(select(Room).order_by(Room.section_name, Room.name)).all()
    return [r for r in rows if r.section_name == section_name] if section_name else rows
@app.get("/api/audit")
def audit(session: Session = Depends(get_session)): return session.exec(select(AuditEvent).order_by(AuditEvent.created_at.desc())).all()

@app.get("/api/staff-load")
def staff_load(session: Session = Depends(get_session)):
    rows = session.exec(select(StaffMember).order_by(StaffMember.role, StaffMember.name)).all()
    blocks = session.exec(select(ScheduleBlock)).all()
    now = datetime.now(timezone.utc)
    return [{"staff_member_id": s.id, "name": s.name, "role": s.role, "skills": s.skills, "on_shift": on_shift(session, s.id or 0, now, now), "active_blocks": len([b for b in blocks if b.assigned_staff_member_id == s.id and b.status != "done"]), "assigned_block_ids": [b.id for b in blocks if b.assigned_staff_member_id == s.id and b.status != "done"]} for s in rows]

@app.get("/api/episode-command/{episode_ref}")
def episode_command(episode_ref: str, session: Session = Depends(get_session)):
    ep = session.exec(select(Episode).where(Episode.episode_ref == episode_ref)).first()
    if not ep: raise HTTPException(status_code=404, detail="Episode not found")
    return {"episode": ep, "patient": session.get(Patient, ep.patient_id), "admissions": session.exec(select(Admission).where(Admission.episode_id == ep.id)).all(), "handovers": session.exec(select(Handover).where(Handover.episode_id == ep.id)).all(), "results": session.exec(select(ResultReview).where(ResultReview.episode_id == ep.id)).all(), "schedule_blocks": session.exec(select(ScheduleBlock).where(ScheduleBlock.episode_id == ep.id).order_by(ScheduleBlock.starts_at)).all(), "message_threads": session.exec(select(MessageThread).where(MessageThread.episode_id == ep.id).order_by(MessageThread.created_at.desc())).all(), "work_items": session.exec(select(WorkItem).where(WorkItem.linked_episode_ref == episode_ref).order_by(WorkItem.created_at.desc())).all(), "room_state": session.exec(select(RoomState).where(RoomState.room_name == ep.current_room_name)).first() if ep.current_room_name else None, "conflicts": [c for c in compute_conflicts(session) if ep.id in c.get("episode_ids", [])]}

@app.get("/api/director-board")
def director_board(session: Session = Depends(get_session)):
    items = session.exec(select(WorkItem).order_by(WorkItem.created_at.desc())).all()
    sections = []
    for name in sorted({i.section_name for i in items if i.section_name}):
        section_items = [i for i in items if i.section_name == name]
        sections.append({"section_name": name, "live": len([i for i in section_items if i.status != "done"]), "red": len([i for i in section_items if i.urgency == "red"]), "unowned": len([i for i in section_items if i.owner_user_id is None])})
    return {"cards": board_cards(items), "section_pressure": sections, "priority_items": [i for i in items if i.urgency == "red" or i.status == "new"][:10]}
@app.get("/api/consult-board")
def consult_board(session: Session = Depends(get_session)):
    items = [i for i in session.exec(select(WorkItem).order_by(WorkItem.created_at.desc())).all() if i.section_name == "Consults"]
    return {"cards": board_cards(items), "room_groups": room_groups(items)}
@app.get("/api/ward-board")
def ward_board(session: Session = Depends(get_session)):
    items = [i for i in session.exec(select(WorkItem).order_by(WorkItem.created_at.desc())).all() if i.section_name in {"Wards", "ICU"}]
    return {"cards": board_cards(items), "room_groups": room_groups(items)}
@app.get("/api/theatre-board")
def theatre_board(session: Session = Depends(get_session)):
    items = [i for i in session.exec(select(WorkItem).order_by(WorkItem.created_at.desc())).all() if i.section_name in {"Theatres", "Recovery"}]
    return {"cards": board_cards(items), "room_groups": room_groups(items)}

@app.post("/api/auth/login-demo")
def login_demo(payload: LoginDemoRequest, session: Session = Depends(get_session)):
    user = session.get(User, payload.user_id)
    if not user: raise HTTPException(status_code=404, detail="User not found")
    return {"user": user, "token": f"demo-token-{user.id}"}
@app.get("/api/work-items")
def work_items(role: str | None = None, session: Session = Depends(get_session)):
    items = session.exec(select(WorkItem).order_by(WorkItem.created_at.desc())).all()
    return [i for i in items if i.owner_role == role] if role else items
@app.post("/api/work-items")
def create_work(payload: WorkItemCreate, session: Session = Depends(get_session)):
    item = WorkItem(**payload.model_dump()); session.add(item); session.commit(); session.refresh(item); log(session, "System", "created", "work_item", item.id or 0, item.title); return item
@app.post("/api/work-items/{item_id}/assign")
def assign_work(item_id: int, payload: WorkItemAssign, session: Session = Depends(get_session)):
    item = session.get(WorkItem, item_id)
    if not item: raise HTTPException(status_code=404, detail="Work item not found")
    item.owner_role = payload.owner_role; item.owner_user_id = payload.owner_user_id; session.add(item); session.commit(); log(session, payload.actor_name, "assigned", "work_item", item.id or 0, f"Assigned to {payload.owner_role}"); return item
@app.post("/api/work-items/{item_id}/status")
def work_status(item_id: int, payload: WorkItemStatusUpdate, session: Session = Depends(get_session)):
    item = session.get(WorkItem, item_id)
    if not item: raise HTTPException(status_code=404, detail="Work item not found")
    item.status = payload.status; item.updated_at = datetime.now(timezone.utc); session.add(item); session.commit(); log(session, payload.actor_name, "status_updated", "work_item", item.id or 0, payload.status); return item

@app.post("/api/schedule/generate")
def generate_schedule(payload: ScheduleGenerateRequest, session: Session = Depends(get_session)):
    ep = session.exec(select(Episode).where(Episode.episode_ref == payload.episode_ref)).first(); proc = session.get(ProcedureType, payload.procedure_type_id)
    if not ep or not proc: raise HTTPException(status_code=404, detail="Episode or procedure not found")
    cp = CaseProcedure(episode_id=ep.id, procedure_type_id=proc.id, scheduled_start=payload.start_time); session.add(cp); session.commit(); session.refresh(cp)
    blocks = []; cur = payload.start_time
    for name, mins in [("prep", proc.prep_min), ("anaesthesia", proc.anaesthesia_min), ("procedure", proc.default_duration_min), ("recovery", proc.recovery_min), ("cleaning", proc.cleaning_min)]:
        b = ScheduleBlock(episode_id=ep.id, case_procedure_id=cp.id, block_type=name, room_name=payload.room_name, owner_role=proc.required_role, starts_at=cur, ends_at=cur + timedelta(minutes=mins)); cur = b.ends_at; session.add(b); blocks.append(b)
    ep.current_phase = "scheduled"; ep.current_room_name = payload.room_name; ep.current_section_name = proc.department; session.add(ep); session.commit(); log(session, payload.actor_name, "schedule_generated", "case_procedure", cp.id or 0, payload.episode_ref); return {"case_procedure": cp, "blocks": blocks}
@app.post("/api/schedule/block/{block_id}/shift")
def shift_block(block_id: int, payload: ScheduleShiftRequest, session: Session = Depends(get_session)):
    block = session.get(ScheduleBlock, block_id)
    if not block: raise HTTPException(status_code=404, detail="Block not found")
    delta = timedelta(minutes=payload.minutes); chain = session.exec(select(ScheduleBlock).where(ScheduleBlock.case_procedure_id == block.case_procedure_id).order_by(ScheduleBlock.starts_at)).all(); found = False
    for b in chain:
        if b.id == block.id: found = True
        if found: b.starts_at += delta; b.ends_at += delta; session.add(b)
    session.commit(); log(session, payload.actor_name, "schedule_shifted", "schedule_block", block_id, str(payload.minutes)); return {"status": "shifted", "block_id": block_id, "minutes": payload.minutes}
@app.post("/api/staff/allocate")
def allocate_staff(payload: StaffAllocateRequest, session: Session = Depends(get_session)):
    block = session.get(ScheduleBlock, payload.schedule_block_id); staff = session.get(StaffMember, payload.staff_member_id)
    if not block or not staff: raise HTTPException(status_code=404, detail="Invalid block or staff")
    if not on_shift(session, staff.id or 0, block.starts_at, block.ends_at): return {"status": "conflict", "detail": "Staff not available"}
    block.owner_role = staff.role; block.assigned_staff_member_id = staff.id; session.add(block); session.commit(); log(session, payload.actor_name, "staff_allocated", "schedule_block", block.id or 0, staff.name); return {"status": "allocated", "staff": staff.name, "staff_member_id": staff.id}

@app.get("/api/conflicts")
def get_conflicts(session: Session = Depends(get_session)): return {"conflicts": compute_conflicts(session)}
@app.get("/api/conflict-actions")
def conflict_actions(session: Session = Depends(get_session)): return session.exec(select(ConflictAction).order_by(ConflictAction.created_at.desc())).all()
@app.post("/api/conflicts/to-work")
def conflict_to_work(conflict_type: str, severity: str, detail: str, session: Session = Depends(get_session)):
    item = WorkItem(title=f"Resolve {conflict_type}", input_type="conflict", source="conflict_engine", category="resolution", description=detail, urgency="red" if severity == "high" else "amber", owner_role="ops_manager", status="new"); session.add(item); session.commit(); session.refresh(item)
    action = ConflictAction(conflict_type=conflict_type, severity=severity, detail=detail, linked_work_item_id=item.id); session.add(action); session.commit(); session.refresh(action); log(session, "System", "conflict_to_work", "work_item", item.id or 0, conflict_type); return {"work_item": item, "conflict_action": action}
@app.post("/api/conflict-actions/{action_id}/resolve")
def resolve_conflict(action_id: int, note: str = "Resolved", session: Session = Depends(get_session)):
    action = session.get(ConflictAction, action_id)
    if not action: raise HTTPException(status_code=404, detail="Conflict action not found")
    action.status = "resolved"; action.resolved_at = datetime.now(timezone.utc); action.resolution_note = note; session.add(action)
    if action.linked_work_item_id:
        item = session.get(WorkItem, action.linked_work_item_id)
        if item: item.status = "done"; item.updated_at = datetime.now(timezone.utc); session.add(item)
    session.commit(); log(session, "System", "conflict_resolved", "conflict_action", action.id or 0, note); return action

@app.post("/api/results/{result_id}/action")
def action_result(result_id: int, payload: ResultActionRequest, session: Session = Depends(get_session)):
    result = session.get(ResultReview, result_id)
    if not result: raise HTTPException(status_code=404, detail="Result not found")
    result.status = payload.status; result.required_action = payload.required_action; result.reviewed_at = datetime.now(timezone.utc); session.add(result); session.commit(); log(session, payload.actor_name, "result_actioned", "result_review", result.id or 0, payload.status); return result
@app.post("/api/messages/thread")
def create_thread(payload: MessageThreadCreate, session: Session = Depends(get_session)):
    episode_id = None
    if payload.episode_ref:
        ep = session.exec(select(Episode).where(Episode.episode_ref == payload.episode_ref)).first()
        if not ep: raise HTTPException(status_code=404, detail="Episode not found")
        episode_id = ep.id
    thread = MessageThread(episode_id=episode_id, source_type=payload.source_type, subject=payload.subject, owner_role=payload.owner_role, owner_user_id=payload.owner_user_id); session.add(thread); session.commit(); session.refresh(thread); return thread
@app.post("/api/messages/{thread_id}")
def add_message(thread_id: int, payload: MessageEntryCreate, session: Session = Depends(get_session)):
    if not session.get(MessageThread, thread_id): raise HTTPException(status_code=404, detail="Thread not found")
    entry = MessageEntry(thread_id=thread_id, sender_name=payload.sender_name, direction=payload.direction, body=payload.body, material_decision_flag=payload.material_decision_flag); session.add(entry); session.commit(); session.refresh(entry); return entry
@app.post("/api/room-states/{room_state_id}/set")
def set_room_state(room_state_id: int, state: str, session: Session = Depends(get_session)):
    room_state = session.get(RoomState, room_state_id)
    if not room_state: raise HTTPException(status_code=404, detail="Room state not found")
    room_state.state = state
    if state == "cleaning" and not room_state.cleaning_due_minutes: room_state.cleaning_due_minutes = 20
    if state == "available": room_state.current_episode_ref = None; room_state.next_episode_ref = None; room_state.cleaning_due_minutes = None
    session.add(room_state); session.commit(); return room_state
