from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from datetime import datetime, timedelta

from app.database import create_db_and_tables, engine, get_session
from app.models import (
    Admission, AuditEvent, Episode, Handover, HospitalSection, Patient,
    ResultReview, Room, RoomState, User, WorkItem,
    ProcedureType, CaseProcedure, ScheduleBlock, MessageThread, MessageEntry
)
from app.schemas import (
    LoginDemoRequest, WorkItemAssign, WorkItemCreate, WorkItemStatusUpdate,
    ScheduleGenerateRequest, ResultActionRequest, MessageThreadCreate, MessageEntryCreate
)
from app.seed import seed_data

app = FastAPI(title="LucyWorks OS API", version="0.2.0")

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

@app.post("/api/schedule/generate")
def generate_schedule(payload: ScheduleGenerateRequest, session: Session = Depends(get_session)):
    episode = session.exec(select(Episode).where(Episode.episode_ref == payload.episode_ref)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    procedure = session.get(ProcedureType, payload.procedure_type_id)
    if not procedure:
        raise HTTPException(status_code=404, detail="Procedure type not found")

    case_proc = CaseProcedure(episode_id=episode.id, procedure_type_id=procedure.id, scheduled_start=payload.start_time)
    session.add(case_proc)
    session.commit()
    session.refresh(case_proc)

    blocks = []
    current = payload.start_time

    def add_block(name, minutes):
        nonlocal current
        block = ScheduleBlock(
            episode_id=episode.id,
            case_procedure_id=case_proc.id,
            block_type=name,
            room_name=payload.room_name,
            owner_role=procedure.required_role,
            starts_at=current,
            ends_at=current + timedelta(minutes=minutes)
        )
        current = block.ends_at
        blocks.append(block)

    add_block("prep", procedure.prep_min)
    add_block("anaesthesia", procedure.anaesthesia_min)
    add_block("procedure", procedure.default_duration_min)
    add_block("recovery", procedure.recovery_min)
    add_block("cleaning", procedure.cleaning_min)

    for b in blocks:
        session.add(b)
    session.commit()

    return {"case_procedure": case_proc, "blocks": blocks}

@app.get("/api/conflicts")
def get_conflicts(session: Session = Depends(get_session)):
    blocks = session.exec(select(ScheduleBlock)).all()
    conflicts = []

    for b1 in blocks:
        for b2 in blocks:
            if b1.id >= b2.id:
                continue
            if b1.room_name == b2.room_name and not (b1.ends_at <= b2.starts_at or b2.ends_at <= b1.starts_at):
                conflicts.append({"type": "room_conflict", "detail": f"{b1.room_name} overlap"})

    return {"conflicts": conflicts}

@app.post("/api/results/{result_id}/action")
def action_result(result_id: int, payload: ResultActionRequest, session: Session = Depends(get_session)):
    result = session.get(ResultReview, result_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    result.status = payload.status
    result.required_action = payload.required_action
    result.reviewed_at = datetime.utcnow()

    session.add(result)
    session.commit()

    return result

@app.post("/api/messages/thread")
def create_thread(payload: MessageThreadCreate, session: Session = Depends(get_session)):
    thread = MessageThread(**payload.model_dump())
    session.add(thread)
    session.commit()
    return thread

@app.post("/api/messages/{thread_id}")
def add_message(thread_id: int, payload: MessageEntryCreate, session: Session = Depends(get_session)):
    entry = MessageEntry(thread_id=thread_id, sender_name=payload.sender_name, direction=payload.direction, body=payload.body, material_decision_flag=payload.material_decision_flag)
    session.add(entry)
    session.commit()
    return entry
