from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.auth import AuthContext, require_authenticated
from app.database import get_session
from app.organisation_onboarding_v27_hardening import set_access_disposition
from app.organisation_onboarding_v27_service import readiness_summary, staff_dict

router = APIRouter(prefix="/api/v27", tags=["organisation-onboarding-v27"])


class AccessDispositionRequest(BaseModel):
    status: str
    reason: str = Field(min_length=3, max_length=1000)


@router.post("/sites/{site_ref}/staff/{staff_ref}/access-disposition")
def update_access_disposition(
    site_ref: str,
    staff_ref: str,
    request: AccessDispositionRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
):
    row = set_access_disposition(session, auth, site_ref, staff_ref, request.status, request.reason)
    session.commit()
    session.refresh(row)
    return {"staff": staff_dict(row), "readiness": readiness_summary(session, site_ref)}
