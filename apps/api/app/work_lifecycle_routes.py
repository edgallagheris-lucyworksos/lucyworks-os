from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.models import AuditEvent, WorkItem

router = APIRouter(prefix="/api/work-lifecycle", tags=["work-lifecycle"])


class Note(BaseModel):
    actor_name: str = "LucyWorks UI"
    note: str = ""


class MovePayload(BaseModel):
    owner_role: str
    owner_user_id: int | None = None
    actor_name: str = "LucyWorks UI"
    note: str = ""


def stamp():
    return datetime.now(timezone.utc)


def log(session: Session, actor: str, action: str, item: WorkItem, note: str):
    event = AuditEvent(actor_name=actor, action=action, entity_type="work_item", entity_id=item.id or 0, summary=note or item.title)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


@router.post("/{item_id}/accept")
def accept_item(item_id: int, payload: Note, session: Session = Depends(get_session)):
    item = session.get(WorkItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Work item not found")
    item.status = "accepted"
    item.updated_at = stamp()
    session.add(item)
    session.commit()
    session.refresh(item)
    event = log(session, payload.actor_name, "work_item_accepted", item, payload.note)
    return {"ok": True, "work_item": item, "audit_event": event}


@router.post("/{item_id}/decline")
def decline_item(item_id: int, payload: Note, session: Session = Depends(get_session)):
    item = session.get(WorkItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Work item not found")
    item.status = "new"
    item.owner_user_id = None
    item.updated_at = stamp()
    session.add(item)
    session.commit()
    session.refresh(item)
    event = log(session, payload.actor_name, "work_item_returned_to_role_queue", item, payload.note)
    return {"ok": True, "work_item": item, "audit_event": event}


@router.post("/{item_id}/move")
def move_item(item_id: int, payload: MovePayload, session: Session = Depends(get_session)):
    item = session.get(WorkItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Work item not found")
    item.owner_role = payload.owner_role
    item.owner_user_id = payload.owner_user_id
    item.status = "new"
    item.updated_at = stamp()
    session.add(item)
    session.commit()
    session.refresh(item)
    event = log(session, payload.actor_name, "work_item_moved", item, payload.note)
    return {"ok": True, "work_item": item, "audit_event": event}


@router.get("/user/{owner_user_id}")
def user_items(owner_user_id: int, session: Session = Depends(get_session)):
    items = session.exec(select(WorkItem).where(WorkItem.owner_user_id == owner_user_id, WorkItem.status != "done").order_by(WorkItem.urgency, WorkItem.created_at)).all()
    return {"count": len(items), "work_items": items}
