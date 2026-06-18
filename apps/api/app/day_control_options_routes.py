from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.assignment_directory_models import AssignmentPersonOption, AssignmentResourceOption
from app.database import get_session

router = APIRouter(prefix="/api/day-control", tags=["day-control"])

DEFAULT_PEOPLE = [(101, "Reception 1", "reception", "front_door"), (102, "Reception 2", "reception", "front_door"), (201, "Insurance Admin", "insurance/admin", "admin"), (301, "Imaging Lead", "imaging lead", "imaging"), (302, "Clinical Lead", "clinical lead", "clinical"), (401, "Surgical Lead", "surgical lead", "theatre"), (402, "Anaesthesia", "anaesthesia", "theatre"), (501, "Nurse 1", "nurse", "ward"), (502, "Nurse 2", "nurse", "ward"), (601, "PCA 1", "PCA", "support"), (701, "Client Contact", "client contact", "client"), (801, "Ops Manager", "ops manager", "ops")]
DEFAULT_RESOURCES = [("reception", "Reception", "front_door"), ("admin-queue", "Admin queue", "admin"), ("consult-room", "Consult room", "consult"), ("mri", "MRI", "imaging"), ("ct", "CT", "imaging"), ("theatre-1", "Theatre 1", "theatre"), ("theatre-2", "Theatre 2", "theatre"), ("recovery", "Recovery", "care"), ("ward", "Ward", "care"), ("client-contact", "Client contact", "communication"), ("whole-hospital", "Whole hospital", "ops")]


class PersonOptionPayload(BaseModel):
    name: str
    role: str
    area: str
    active: bool = True


class ResourceOptionPayload(BaseModel):
    id: str
    name: str
    type: str
    active: bool = True


def _payload(payload: BaseModel) -> dict:
    return payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()


def _seed(session: Session) -> None:
    if not session.exec(select(AssignmentPersonOption)).first():
        for item_id, name, role, area in DEFAULT_PEOPLE:
            session.add(AssignmentPersonOption(id=item_id, name=name, role=role, area=area))
    if not session.exec(select(AssignmentResourceOption)).first():
        for item_id, name, item_type in DEFAULT_RESOURCES:
            session.add(AssignmentResourceOption(id=item_id, name=name, type=item_type))
    session.commit()


def _person(row: AssignmentPersonOption) -> dict[str, object]:
    return {"id": row.id, "name": row.name, "role": row.role, "area": row.area, "active": row.active}


def _resource(row: AssignmentResourceOption) -> dict[str, object]:
    return {"id": row.id, "name": row.name, "type": row.type, "active": row.active}


@router.get("/staff-options")
def staff_options(session: Session = Depends(get_session)) -> dict[str, list[dict[str, object]]]:
    _seed(session)
    rows = session.exec(select(AssignmentPersonOption).where(AssignmentPersonOption.active == True).order_by(AssignmentPersonOption.area, AssignmentPersonOption.name)).all()
    return {"staff": [_person(row) for row in rows]}


@router.post("/staff-options")
def create_staff_option(payload: PersonOptionPayload, session: Session = Depends(get_session)) -> dict[str, object]:
    row = AssignmentPersonOption(**_payload(payload))
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"staff": _person(row)}


@router.patch("/staff-options/{person_id}")
def update_staff_option(person_id: int, payload: PersonOptionPayload, session: Session = Depends(get_session)) -> dict[str, object]:
    row = session.get(AssignmentPersonOption, person_id)
    if not row:
        raise HTTPException(status_code=404, detail="person option not found")
    for key, value in _payload(payload).items():
        setattr(row, key, value)
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"staff": _person(row)}


@router.get("/resource-options")
def resource_options(session: Session = Depends(get_session)) -> dict[str, list[dict[str, object]]]:
    _seed(session)
    rows = session.exec(select(AssignmentResourceOption).where(AssignmentResourceOption.active == True).order_by(AssignmentResourceOption.type, AssignmentResourceOption.name)).all()
    return {"resources": [_resource(row) for row in rows]}


@router.post("/resource-options")
def create_resource_option(payload: ResourceOptionPayload, session: Session = Depends(get_session)) -> dict[str, object]:
    row = AssignmentResourceOption(**_payload(payload))
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"resource": _resource(row)}


@router.patch("/resource-options/{resource_id}")
def update_resource_option(resource_id: str, payload: ResourceOptionPayload, session: Session = Depends(get_session)) -> dict[str, object]:
    row = session.get(AssignmentResourceOption, resource_id)
    if not row:
        raise HTTPException(status_code=404, detail="resource option not found")
    for key, value in _payload(payload).items():
        setattr(row, key, value)
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"resource": _resource(row)}
