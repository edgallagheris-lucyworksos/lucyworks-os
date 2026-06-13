from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.database import get_session
from app.models import AuditEvent, WorkItem

router = APIRouter(prefix="/api/queue", tags=["queue"])


class QueuePayload(BaseModel):
    title: str
    role: str
    queue: str
    urgency: str = "amber"
    detail: str = ""
    actor: str = "LucyWorks UI"


@router.post("/work-item")
def create_queue_item(payload: QueuePayload, session: Session = Depends(get_session)):
    item = WorkItem(
        title=payload.title,
        input_type="drawer",
        source="lucyworks",
        category=payload.queue,
        description=payload.detail,
        urgency=payload.urgency,
        owner_role=payload.role,
        status="new",
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    event = AuditEvent(actor_name=payload.actor, action="queue_item_created", entity_type="work_item", entity_id=item.id or 0, summary=payload.detail)
    session.add(event)
    session.commit()
    session.refresh(event)
    return {"ok": True, "work_item": item, "audit_event": event}
