from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.database import get_session
from app.models import AuditEvent, WorkItem

router = APIRouter()


def row_dict(obj):
    mapper = getattr(obj, "__mapper__", None)
    if mapper is None:
        return obj
    return {col.key: getattr(obj, col.key) for col in mapper.columns}


class CapturePayload(BaseModel):
    title: str
    description: str
    input_type: str = "mobile_capture"
    source: str = "phone"
    category: str = "ops"
    urgency: str = "amber"
    owner_role: str = "ops_manager"
    section_name: str | None = None
    room_name: str | None = None
    patient_location_label: str | None = None
    linked_patient_name: str | None = None
    linked_episode_ref: str | None = None
    actor_name: str = "Mobile Capture"


@router.post("/api/input/capture")
def capture_work_item(payload: CapturePayload, session: Session = Depends(get_session)):
    item = WorkItem(
        title=payload.title.strip() or "Untitled capture",
        input_type=payload.input_type,
        source=payload.source,
        category=payload.category,
        description=payload.description.strip(),
        urgency=payload.urgency,
        owner_role=payload.owner_role,
        section_name=payload.section_name,
        room_name=payload.room_name,
        patient_location_label=payload.patient_location_label,
        linked_patient_name=payload.linked_patient_name,
        linked_episode_ref=payload.linked_episode_ref,
        status="new",
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    session.add(AuditEvent(
        actor_name=payload.actor_name,
        action="captured",
        entity_type="work_item",
        entity_id=item.id or 0,
        summary=f"Captured mobile input: {item.title}",
    ))
    session.commit()
    return {"ok": True, "work_item": row_dict(item)}
