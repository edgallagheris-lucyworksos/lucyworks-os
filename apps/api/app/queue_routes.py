from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.models import AuditEvent, Shift, StaffMember, WorkItem
from app.staff_assignment import acceptable_staff_roles

router = APIRouter(prefix="/api/queue", tags=["queue"])


class QueuePayload(BaseModel):
    title: str
    role: str
    queue: str
    urgency: str = "amber"
    detail: str = ""
    actor: str = "LucyWorks UI"


def now_utc():
    return datetime.now(timezone.utc)


def active_shift_staff_ids(session: Session) -> set[int]:
    now = now_utc()
    shifts = session.exec(select(Shift).where(Shift.starts_at <= now, Shift.ends_at >= now, Shift.status != "cancelled")).all()
    return {shift.staff_member_id for shift in shifts}


def workload_by_user(session: Session) -> dict[int, int]:
    open_items = session.exec(select(WorkItem).where(WorkItem.status != "done")).all()
    loads: dict[int, int] = {}
    for item in open_items:
        if item.owner_user_id is not None:
            loads[item.owner_user_id] = loads.get(item.owner_user_id, 0) + 1
    return loads


def skill_score(member: StaffMember, queue: str) -> int:
    skills = (member.skills or "").lower()
    queue_token = queue.replace("_queue", "").replace("_", " ").lower()
    return 0 if queue_token in skills else 1


def pick_staff(session: Session, role: str, queue: str):
    allowed = acceptable_staff_roles(role, queue)
    active_shift_ids = active_shift_staff_ids(session)
    loads = workload_by_user(session)
    staff = session.exec(select(StaffMember).where(StaffMember.active == True).order_by(StaffMember.role, StaffMember.name)).all()
    candidates = [member for member in staff if member.role in allowed]
    if not candidates:
        return None
    on_shift = [member for member in candidates if member.id in active_shift_ids]
    pool = on_shift or candidates
    return sorted(pool, key=lambda member: (loads.get(member.user_id or -1, 0), skill_score(member, queue), member.role, member.name))[0]


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
    return {"ok": True, "work_item": item, "audit_event": event, "routed_to": routed_to, "matched_staff_role": staff.role if staff else None, "matched_staff_id": staff.id if staff else None}
