from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from app.auth import AuthContext, require_roles
from app.bvs_v6_rota_service import (
    exception_dict,
    roster,
    rota_assessment,
    shift_dict,
    upsert_exception,
    upsert_shift,
)
from app.database import get_session

router = APIRouter(prefix="/api/bvs-v6/rota", tags=["bvs-workforce-rota-v6"])

READ_ROLES = ("admin", "clinician", "clinical_director", "governance_lead", "hospital_director", "nurse", "ops_manager", "senior_clinician", "supervisor")
WRITE_ROLES = ("admin", "clinical_director", "governance_lead", "hospital_director", "ops_manager", "supervisor")


class ShiftPayload(BaseModel):
    expectedVersion: int | None = None
    staffRef: str | None = None
    departmentRef: str | None = None
    areaRef: str | None = None
    startsAt: str | None = None
    endsAt: str | None = None
    shiftType: str | None = None
    status: str | None = None
    onCall: bool | None = None
    sourceStatus: str | None = None
    overrideReason: str | None = None
    reason: str | None = None


class AvailabilityPayload(BaseModel):
    expectedVersion: int | None = None
    staffRef: str | None = None
    startsAt: str | None = None
    endsAt: str | None = None
    exceptionType: str | None = None
    status: str | None = None
    detail: str | None = None
    sourceStatus: str | None = None
    reason: str | None = None


def translated(exc: Exception) -> HTTPException:
    if isinstance(exc, RuntimeError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


@router.get("")
def get_roster(
    startsAt: str | None = Query(default=None),
    endsAt: str | None = Query(default=None),
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    start = datetime.fromisoformat(startsAt.replace("Z", "+00:00")) if startsAt else None
    end = datetime.fromisoformat(endsAt.replace("Z", "+00:00")) if endsAt else None
    return roster(session, start, end)


@router.put("/shifts/{shift_ref}")
def put_shift(
    shift_ref: str,
    payload: ShiftPayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    data = payload.model_dump(exclude_none=True)
    if data.get("expectedVersion") is None and (not data.get("staffRef") or not data.get("departmentRef") or not data.get("startsAt") or not data.get("endsAt")):
        raise HTTPException(status_code=400, detail="new shifts require staffRef, departmentRef, startsAt and endsAt")
    try:
        row = upsert_shift(session, shift_ref, data, auth)
        session.commit()
        session.refresh(row)
        return {"shift": shift_dict(row)}
    except Exception as exc:
        session.rollback()
        raise translated(exc) from exc


@router.put("/availability/{exception_ref}")
def put_availability(
    exception_ref: str,
    payload: AvailabilityPayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    data = payload.model_dump(exclude_none=True)
    if data.get("expectedVersion") is None and (not data.get("staffRef") or not data.get("startsAt") or not data.get("endsAt")):
        raise HTTPException(status_code=400, detail="new availability exceptions require staffRef, startsAt and endsAt")
    try:
        row = upsert_exception(session, exception_ref, data, auth)
        session.commit()
        session.refresh(row)
        return {"availabilityException": exception_dict(row)}
    except Exception as exc:
        session.rollback()
        raise translated(exc) from exc


@router.get("/assessment")
def get_assessment(
    at: str | None = Query(default=None),
    restThresholdHours: float = Query(default=11.0, ge=0, le=24),
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_roles(*READ_ROLES)),
) -> dict[str, Any]:
    assessed_at = datetime.fromisoformat(at.replace("Z", "+00:00")) if at else datetime.now(timezone.utc)
    return rota_assessment(session, assessed_at, restThresholdHours)
