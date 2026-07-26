from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.auth import AuthContext, require_roles
from app.database import get_session
from app.models import AuditEvent, WorkItem

router = APIRouter()
CAPTURE_ROLES = ("ops_manager", "clinical_director", "clinician", "nurse", "admin")
VALID_URGENCIES = {"green", "amber", "red"}


def row_dict(obj):
    mapper = getattr(obj, "__mapper__", None)
    if mapper is None:
        return obj
    return {col.key: getattr(obj, col.key) for col in mapper.columns}


class CapturePayload(BaseModel):
    title: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=10000)
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


@router.post("/api/input/capture")
def capture_work_item(
    payload: CapturePayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CAPTURE_ROLES)),
):
    title = payload.title.strip()
    description = payload.description.strip()
    if not title and not description:
        raise HTTPException(status_code=422, detail="title or description is required")
    if payload.urgency not in VALID_URGENCIES:
        raise HTTPException(status_code=422, detail="urgency must be green, amber or red")

    item = WorkItem(
        title=title or description[:80] or "Untitled capture",
        input_type=payload.input_type,
        source=payload.source,
        category=payload.category,
        description=description,
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
        actor_name=auth.actor_name,
        action="captured",
        entity_type="work_item",
        entity_id=item.id or 0,
        summary=f"Captured mobile input: {item.title}",
    ))
    session.commit()
    return {"ok": True, "work_item": row_dict(item)}
