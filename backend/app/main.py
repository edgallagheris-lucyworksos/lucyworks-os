from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine, get_session
from app.models import (
    Admission,
    AuditEvent,
    Episode,
    Handover,
    HospitalSection,
    Patient,
    ResultReview,
    Room,
    RoomState,
    User,
    WorkItem,
)
from app.schemas import LoginDemoRequest, WorkItemAssign, WorkItemCreate, WorkItemStatusUpdate
from app.seed import seed_data

app = FastAPI(title="LucyWorks OS API", version="0.1.0")

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
    statement = select(WorkItem).order_by(WorkItem.created_at.desc())
    items = session.exec(statement).all()
    if role:
        items = [item for item in items if item.owner_role == role]
    return items


@app.post("/api/work-items")
def create_work_item(payload: WorkItemCreate, session: Session = Depends(get_session)):
    item = WorkItem(**payload.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)

    event = AuditEvent(
        actor_name="System",
        action="created",
        entity_type="work_item",
        entity_id=item.id or 0,
        summary=f"Created work item: {item.title}",
    )
    session.add(event)
    session.commit()
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

    event = AuditEvent(
        actor_name=payload.actor_name,
        action="assigned",
        entity_type="work_item",
        entity_id=item.id or 0,
        summary=f"Assigned to role {payload.owner_role}",
    )
    session.add(event)
    session.commit()
    return item


@app.post("/api/work-items/{item_id}/status")
def update_work_item_status(item_id: int, payload: WorkItemStatusUpdate, session: Session = Depends(get_session)):
    item = session.get(WorkItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Work item not found")
    item.status = payload.status
    session.add(item)
    session.commit()
    session.refresh(item)

    event = AuditEvent(
        actor_name=payload.actor_name,
        action="status_updated",
        entity_type="work_item",
        entity_id=item.id or 0,
        summary=f"Status changed to {payload.status}",
    )
    session.add(event)
    session.commit()
    return item


@app.get("/api/audit")
def list_audit(session: Session = Depends(get_session)):
    return session.exec(select(AuditEvent).order_by(AuditEvent.created_at.desc())).all()


@app.get("/api/pulse")
def pulse(session: Session = Depends(get_session)):
    items = session.exec(select(WorkItem)).all()
    return {
        "total_work_items": len(items),
        "red_items": len([i for i in items if i.urgency == "red"]),
        "new_items": len([i for i in items if i.status == "new"]),
        "in_progress_items": len([i for i in items if i.status == "in_progress"]),
        "unowned_items": len([i for i in items if i.owner_user_id is None]),
        "wards_items": len([i for i in items if i.section_name == "Wards"]),
        "theatres_items": len([i for i in items if i.section_name == "Theatres"]),
        "consult_items": len([i for i in items if i.section_name == "Consults"]),
    }


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
        section_pressure.append({"section_name": name, "live": len([item for item in section_items if item.status != "done"]), "red": len([item for item in section_items if item.urgency == "red"]), "unowned": len([item for item in section_items if item.owner_user_id is None])})

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
        room_groups.append({"room_name": room_name, "section_name": room_items[0].section_name if room_items else None, "live": len([item for item in room_items if item.status != "done"]), "red": len([item for item in room_items if item.urgency == "red"]), "items": room_items})
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
        room_groups.append({"room_name": room_name, "section_name": room_items[0].section_name if room_items else None, "live": len([item for item in room_items if item.status != "done"]), "red": len([item for item in room_items if item.urgency == "red"]), "items": room_items})
    return {"cards": cards, "room_groups": room_groups}
