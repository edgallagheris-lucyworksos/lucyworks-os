from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth import AuthContext, require_roles
from app.database import get_session
from app.evidence_approval_models import ApprovalTask
from app.evidence_event_models import EvidenceEvent
from app.evidence_service import approval_reason_for, create_evidence_event, required_approval_role

router = APIRouter(prefix="/api/evidence/approvals", tags=["evidence-approvals"])

APPROVER_ROLES = {
    "clinical_director",
    "ops_manager",
    "hospital_director",
    "senior_clinician",
    "supervisor",
    "governance_lead",
}


class ApprovalDecision(BaseModel):
    decision: str
    note: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _approval_dict(row: ApprovalTask) -> dict[str, Any]:
    return {
        "id": row.id,
        "evidenceEventRef": row.evidence_event_ref,
        "patientCaseId": row.patient_case_id,
        "referralEpisodeId": row.referral_episode_id,
        "status": row.status,
        "requiredRole": row.required_role,
        "reason": row.reason,
        "riskLevel": row.risk_level,
        "sourceModule": row.source_module,
        "requestedBy": row.requested_by,
        "requestedAt": row.requested_at.isoformat() if row.requested_at else None,
        "decidedBy": row.decided_by,
        "decidedByRole": row.decided_by_role,
        "decisionNote": row.decision_note,
        "decidedAt": row.decided_at.isoformat() if row.decided_at else None,
    }


def _event_dict(row: EvidenceEvent) -> dict[str, Any]:
    return {
        "eventRef": row.event_ref,
        "eventType": row.event_type,
        "patientCaseId": row.patient_case_id,
        "referralEpisodeId": row.referral_episode_id,
        "actorName": row.actor_name,
        "actorRole": row.actor_role,
        "actorAuthSource": row.actor_auth_source,
        "professionalRole": row.professional_role,
        "action": row.action,
        "reason": row.reason,
        "justification": row.justification,
        "aiSystem": row.ai_system,
        "aiModel": row.ai_model,
        "humanReviewer": row.human_reviewer,
        "humanReviewStatus": row.human_review_status,
        "supervisorApprovalStatus": row.supervisor_approval_status,
        "overrideReason": row.override_reason,
        "complianceDomain": row.compliance_domain,
        "riskLevel": row.risk_level,
        "sourceModule": row.source_module,
        "eventHash": row.event_hash,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def _backfill_legacy_approval_tasks(session: Session) -> None:
    """Create tasks for legacy events written before automatic task creation."""

    existing_refs = {row.evidence_event_ref for row in session.exec(select(ApprovalTask)).all()}
    events = session.exec(select(EvidenceEvent).order_by(EvidenceEvent.created_at.desc())).all()
    created = False
    for event in events:
        reason = approval_reason_for(event)
        if not reason or event.event_ref in existing_refs:
            continue
        session.add(
            ApprovalTask(
                evidence_event_ref=event.event_ref,
                patient_case_id=event.patient_case_id,
                referral_episode_id=event.referral_episode_id,
                status="pending",
                required_role=required_approval_role(event),
                reason=reason,
                risk_level=event.risk_level,
                source_module=event.source_module,
                requested_by=event.actor_name,
            )
        )
        created = True
    if created:
        session.commit()


@router.get("")
def list_approvals(
    status: str | None = None,
    patient_case_id: str | None = None,
    referral_episode_id: str | None = None,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    _backfill_legacy_approval_tasks(session)
    query = select(ApprovalTask).order_by(ApprovalTask.requested_at.desc())
    if status:
        query = query.where(ApprovalTask.status == status)
    if patient_case_id:
        query = query.where(ApprovalTask.patient_case_id == patient_case_id)
    if referral_episode_id:
        query = query.where(ApprovalTask.referral_episode_id == referral_episode_id)
    rows = session.exec(query).all()
    event_refs = [row.evidence_event_ref for row in rows]
    events = session.exec(select(EvidenceEvent).where(EvidenceEvent.event_ref.in_(event_refs))).all() if event_refs else []
    event_by_ref = {event.event_ref: event for event in events}
    return {
        "approvals": [
            {
                **_approval_dict(row),
                "event": _event_dict(event_by_ref[row.evidence_event_ref]) if row.evidence_event_ref in event_by_ref else None,
            }
            for row in rows
        ],
        "count": len(rows),
    }


@router.patch("/{approval_id}")
def decide_approval(
    approval_id: int,
    payload: ApprovalDecision,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*APPROVER_ROLES)),
) -> dict[str, Any]:
    row = session.get(ApprovalTask, approval_id)
    if not row:
        raise HTTPException(status_code=404, detail="approval task not found")
    if payload.decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="decision must be approved or rejected")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail="approval task already decided")

    source_event = session.exec(select(EvidenceEvent).where(EvidenceEvent.event_ref == row.evidence_event_ref)).first()
    if not source_event:
        raise HTTPException(status_code=409, detail="source evidence event is missing")

    row.status = payload.decision
    row.decided_by = auth.actor_name
    row.decided_by_role = auth.role
    row.decision_note = payload.note
    row.decided_at = _now()
    session.add(row)

    # The source event is immutable. Approval is a new linked event, never a
    # mutation of the original evidence/hash.
    decision_event, _ = create_evidence_event(
        session,
        event_type="approval_decision",
        action=f"approval {payload.decision}",
        patient_case_id=row.patient_case_id,
        referral_episode_id=row.referral_episode_id,
        actor_id=auth.actor_id,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        professional_role=auth.role,
        previous_state={"approvalStatus": "pending"},
        new_state={"approvalStatus": payload.decision, "approvalTaskId": row.id},
        reason=row.reason,
        justification=payload.note,
        evidence_links=[
            {"type": "evidence_event", "id": row.evidence_event_ref, "hash": source_event.event_hash},
            {"type": "approval_task", "id": row.id},
        ],
        supervisor_name=auth.actor_name,
        supervisor_approval_status=payload.decision,
        compliance_domain="governance_approval",
        risk_level="green" if payload.decision == "approved" else "red",
        source_module="evidence-approval",
        source_record_ref=str(row.id),
        causation_event_ref=row.evidence_event_ref,
        correlation_id=source_event.correlation_id,
        entity_type="approval_task",
        entity_id=str(row.id),
        idempotency_key=f"approval:{row.id}:{payload.decision}",
    )
    session.commit()
    session.refresh(row)
    session.refresh(decision_event)
    return {"approval": _approval_dict(row), "decisionEvent": _event_dict(decision_event)}
