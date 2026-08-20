from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.evidence_models import EvidenceEvent, VerificationRecord
from app.evidence_service import record_evidence

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EvidencePayload(BaseModel):
    event_type: str
    actor_name: str
    actor_role: Optional[str] = None
    authority_basis: Optional[str] = None
    entity_type: str
    entity_id: str
    episode_id: Optional[int] = None
    action: str
    state_before: Any = None
    state_after: Any = None
    reason: Optional[str] = None
    evidence_refs: list[str] = []
    source_system: str = "lucyworks"
    correlation_id: Optional[str] = None


class VerificationCreate(BaseModel):
    episode_id: Optional[int] = None
    entity_type: str
    entity_id: str
    content_type: str
    original_content: str
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    provenance: Optional[str] = None


class VerificationDecision(BaseModel):
    status: str
    verified_by: str
    verifier_role: Optional[str] = None
    final_content: Optional[str] = None
    reason: Optional[str] = None


@router.post("/events", response_model=EvidenceEvent)
def create_evidence(payload: EvidencePayload, session: Session = Depends(get_session)):
    return record_evidence(session, **payload.model_dump())


@router.get("/events", response_model=list[EvidenceEvent])
def list_evidence(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    episode_id: Optional[int] = None,
    correlation_id: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    statement = select(EvidenceEvent)
    if entity_type:
        statement = statement.where(EvidenceEvent.entity_type == entity_type)
    if entity_id:
        statement = statement.where(EvidenceEvent.entity_id == entity_id)
    if episode_id is not None:
        statement = statement.where(EvidenceEvent.episode_id == episode_id)
    if correlation_id:
        statement = statement.where(EvidenceEvent.correlation_id == correlation_id)
    statement = statement.order_by(EvidenceEvent.created_at.desc()).limit(limit)
    return list(session.exec(statement).all())


@router.post("/verifications", response_model=VerificationRecord)
def create_verification(payload: VerificationCreate, session: Session = Depends(get_session)):
    row = VerificationRecord(**payload.model_dump())
    session.add(row)
    session.commit()
    session.refresh(row)
    record_evidence(
        session,
        event_type="ai_verification",
        actor_name="System",
        action="generated",
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        episode_id=payload.episode_id,
        state_after={"verification_id": row.id, "status": row.status, "content_type": row.content_type},
        reason="AI-generated content awaiting human verification",
        evidence_refs=[f"verification:{row.id}"],
    )
    return row


@router.post("/verifications/{verification_id}/decision", response_model=VerificationRecord)
def decide_verification(verification_id: int, payload: VerificationDecision, session: Session = Depends(get_session)):
    if payload.status not in {"verified", "amended", "rejected"}:
        raise HTTPException(status_code=422, detail="status must be verified, amended, or rejected")
    row = session.get(VerificationRecord, verification_id)
    if not row:
        raise HTTPException(status_code=404, detail="Verification record not found")
    if row.status != "awaiting_verification":
        raise HTTPException(status_code=409, detail="Verification decision is already final")
    if payload.status == "amended" and not payload.final_content:
        raise HTTPException(status_code=422, detail="amended verification requires final_content")

    before = {"status": row.status, "final_content": row.final_content}
    row.status = payload.status
    row.verified_by = payload.verified_by
    row.verifier_role = payload.verifier_role
    row.final_content = payload.final_content if payload.final_content is not None else (row.original_content if payload.status == "verified" else None)
    row.verification_reason = payload.reason
    row.verified_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)

    record_evidence(
        session,
        event_type="ai_verification",
        actor_name=payload.verified_by,
        actor_role=payload.verifier_role,
        authority_basis="human_verification",
        action=payload.status,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        episode_id=row.episode_id,
        state_before=before,
        state_after={"status": row.status, "final_content": row.final_content},
        reason=payload.reason,
        evidence_refs=[f"verification:{row.id}"],
    )
    return row
