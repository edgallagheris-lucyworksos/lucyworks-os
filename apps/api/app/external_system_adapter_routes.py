from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.auth import AuthContext, require_roles
from app.database import get_session
from app.external_system_adapter_runtime import ingest_normalized_event

router = APIRouter(prefix="/api/integrations/inbound", tags=["external-system-adapter"])
INGEST_ROLES = ("admin", "ops_manager", "hospital_director", "governance_lead")


class NormalizedInboundEvent(BaseModel):
    externalEventId: str = Field(min_length=1, max_length=300)
    eventType: str = Field(min_length=1, max_length=200)
    payload: dict[str, Any] = Field(default_factory=dict)


@router.post("/{connector_ref}/events")
def ingest_event(
    connector_ref: str,
    payload: NormalizedInboundEvent,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_roles(*INGEST_ROLES)),
) -> dict[str, Any]:
    try:
        result = ingest_normalized_event(session, connector_ref, payload.model_dump())
        session.commit()
        return {
            "status": result.status,
            "eventRef": result.event_ref,
            "episodeRef": result.episode_ref,
            "patientRef": result.patient_ref,
            "reconciliationRef": result.reconciliation_ref,
            "duplicate": result.duplicate,
            "boundary": "Inbound only. This endpoint cannot write back to the vendor system.",
        }
    except RuntimeError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
