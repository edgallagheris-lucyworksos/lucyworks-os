from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.evidence_approval_models import ApprovalTask
from app.evidence_event_models import EvidenceEvent

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
    decidedBy: str = "frontend"
    decidedByRole: str = "ops_manager"
    note: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _needs_approval(event: EvidenceEvent) -> str | None:
    if event.supervisor_required:
        return "supervisor approval explicitly required"
    if event.supervisor_approval_status in {"required", "pending"}:
        return "supervisor approval status requires review"
    if event.risk_level == "red":
        return "red-risk evidence event"
    if event.override_reason:
        return "override requires named approval"
    if event.ai_system and event.human_review_status in {"not_required", "required", "pending", ""}:
        return "AI-linked evidence lacks completed human review"
    return None


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
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def _ensure_approval_tasks(session: Session) -> None:
    existing_refs = {row.evidence_event_ref for row in session.exec(select(ApprovalTask)).all()}
    events = session.exec(select(EvidenceEvent).order_by(EvidenceEvent.created_at.desc())).all()
    created = False
    for event in events:
        reason = _needs_approval(event)
        if not reason or event.event_ref in existing_refs:
            continue
        task = ApprovalTask(
            evidence_event_ref=event.event_ref,
            patient_case_id=event.patient_case_id,
            referral_episode_id=event.referral_episode_id,
            status="pending",
            required_role="clinical_director_or_ops_manager",
            reason=reason,
            risk_level=event.risk_level,
            source_module=event.source_module,
            requested_by=event.actor_name,
        )
        session.add(task)
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
    _ensure_approval_tasks(session)
    rows = session.exec(select(ApprovalTask).order_by(ApprovalTask.requested_at.desc())).all()
    if status:
        rows = [row for row in rows if row.status == status]
    if patient_case_id:
        rows = [row for row in rows if row.patient_case_id == patient_case_id]
    if referral_episode_id:
        rows = [row for row in rows if row.referral_episode_id == referral_episode_id]
    event_refs = {row.evidence_event_ref for row in rows}
    events = session.exec(select(EvidenceEvent)).all()
    event_by_ref = {event.event_ref: event for event in events if event.event_ref in event_refs}
    return {
        "approvals": [{**_approval_dict(row), "event": _event_dict(event_by_ref[row.evidence_event_ref]) if row.evidence_event_ref in event_by_ref else None} for row in rows],
        "count": len(rows),
    }


@router.patch("/{approval_id}")
def decide_approval(approval_id: int, payload: ApprovalDecision, session: Session = Depends(get_session)) -> dict[str, Any]:
    row = session.get(ApprovalTask, approval_id)
    if not row:
        raise HTTPException(status_code=404, detail="approval task not found")
    if payload.decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="decision must be approved or rejected")
    if payload.decidedByRole not in APPROVER_ROLES:
        raise HTTPException(status_code=403, detail="approver role not permitted")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail="approval task already decided")

    row.status = payload.decision
    row.decided_by = payload.decidedBy
    row.decided_by_role = payload.decidedByRole
    row.decision_note = payload.note
    row.decided_at = _now()
    session.add(row)

    event = session.exec(select(EvidenceEvent).where(EvidenceEvent.event_ref == row.evidence_event_ref)).first()
    if event:
        event.supervisor_name = payload.decidedBy
        event.supervisor_approval_status = payload.decision
        session.add(event)
        decision_event = EvidenceEvent(
            event_ref=f"approval-{int(_now().timestamp() * 1000)}",
            event_type="approval_decision",
            patient_case_id=row.patient_case_id,
            referral_episode_id=row.referral_episode_id,
            actor_name=payload.decidedBy,
            actor_role=payload.decidedByRole,
            professional_role=payload.decidedByRole,
            action=f"approval {payload.decision}",
            reason=row.reason,
            justification=payload.note,
            evidence_links_json=json.dumps([{"type": "evidence_event", "id": row.evidence_event_ref}, {"type": "approval_task", "id": row.id}]),
            supervisor_name=payload.decidedBy,
            supervisor_approval_status=payload.decision,
            compliance_domain="governance_approval",
            risk_level=row.risk_level,
            source_module="evidence-approval",
        )
        session.add(decision_event)
    session.commit()
    session.refresh(row)
    return {"approval": _approval_dict(row)}
