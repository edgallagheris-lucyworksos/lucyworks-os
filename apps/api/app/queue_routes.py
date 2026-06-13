from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.models import AuditEvent, StaffMember, WorkItem
from app.staff_assignment import acceptable_staff_roles

router = APIRouter(prefix="/api/queue", tags=["queue"])


class QueuePayload(BaseModel):
    title: str
    role: str
    queue: str
    urgency: str = "amber"
    detail: str = ""
    actor: str = "LucyWorks UI"


def pick_staff(session: Session, role: str, queue: str):
    allowed = acceptable_staff_roles(role, queue)
    staff = session.exec(select(StaffMember).where(StaffMember.active == True).order_by(StaffMember.role, StaffMember.name)).all()
    return next((member for member in staff if member.role in allowed), None)


@router.post("/work-item")
def create_queue_item(payload: QueuePayload, session: Session = Depends(get_session)):
    staff = pick_staff(session, payload.role, payload.queue)
    item = WorkItem(
        title=payload.title,
        input_type="drawer",
        source="lucyworks",
        category=payload.queue,
        description=payload.detail,
        urgency=payload.urgency,
        owner_role=payload.role,
        owner_user_id=staff.user_id if staff else None,
        status="new",
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    routed_to = staff.name if staff else payload.role
    event = AuditEvent(actor_name=payload.actor, action="queue_item_created", entity_type="work_item", entity_id=item.id or 0, summary=f"{payload.detail} -> {routed_to}")
    session.add(event)
    session.commit()
    session.refresh(event)
    return {"ok": True, "work_item": item, "audit_event": event, "routed_to": routed_to, "matched_staff_role": staff.role if staff else None}
