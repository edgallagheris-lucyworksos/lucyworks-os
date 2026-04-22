from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine, get_session
from app.models import AuditEvent, User, WorkItem
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
    }
