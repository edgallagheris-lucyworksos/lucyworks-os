from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth import AuthContext, require_authenticated, require_roles
from app.control_plane_models import AccountableHandover, CriticalResultAcknowledgement
from app.control_plane_routes import (
    CriticalResultCreate,
    CriticalResultDecision,
    HandoverCreate,
    HandoverDecision,
    critical_result_dict,
    handover_dict,
)
from app.database import get_session
from app.evidence_service import create_evidence_event
from app.hr_models import FatigueRiskRecord, HRApprovalGate, OnCallAssignment, OvertimeRequest
from app.models import Shift
from app.patient_care_models import PatientWorkflowEvent, ReferralEpisode
from app.patient_care_routes import EpisodeStatePatch, WorkflowEventCreate
from app.safety_control_v25_service import (
    CLINICAL_ROLES,
    SENIOR_ROLES,
    action_dict,
    complete_action,
    create_action,
    create_decision,
    create_escalation,
    create_record,
    decision_dict,
    escalation_dict,
    require_record,
    sensitive_record_dict,
    utc_now,
)

router = APIRouter(tags=["cross-system-safety-bridge-v25"])
SENIOR_ROLE_TUPLE = tuple(sorted(SENIOR_ROLES))
CLINICAL_ROLE_TUPLE = tuple(sorted(CLINICAL_ROLES | SENIOR_ROLES))


def _episode_dict(row: ReferralEpisode) -> dict[str, Any]:
    return {
        "id": row.id,
        "patientCaseId": row.patient_case_id,
        "episodeRef": row.episode_ref,
        "stage": row.stage,
        "ownerRole": row.owner_role,
        "ownerName": row.owner_name,
        "currentLocation": row.current_location,
        "nextAction": row.next_action,
        "blocker": row.blocker,
        "status": row.status,
        "consentStatus": row.consent_status,
        "estimateStatus": row.estimate_status,
        "insuranceStatus": row.insurance_status,
        "pharmacyReady": row.pharmacy_ready,
        "ownerUpdated": row.owner_updated,
        "referringVetReportSent": row.referring_vet_report_sent,
        "dischargeClear": row.discharge_clear,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def _workflow_event_dict(row: PatientWorkflowEvent) -> dict[str, Any]:
    return {
        "id": row.id,
        "episodeId": row.episode_id,
        "patientCaseId": row.patient_case_id,
        "eventType": row.event_type,
        "action": row.action,
        "actor": row.actor,
        "note": row.note,
        "sourceBlockId": row.source_block_id,
        "atTime": row.at_time,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def _slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    return "-".join(part for part in cleaned.split("-") if part) or "issue"


def _safety_by_source(session: Session, source_module: str, source_record_ref: str):
    from app.safety_control_v25_models import SafetyRecordV25

    return session.exec(
        select(SafetyRecordV25).where(
            SafetyRecordV25.source_module == source_module,
            SafetyRecordV25.source_record_ref == source_record_ref,
        )
    ).first()


@router.patch("/api/patient-care/episodes/{episode_id}/state")
def secure_update_episode_state(
    episode_id: str,
    payload: EpisodeStatePatch,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CLINICAL_ROLE_TUPLE)),
) -> dict[str, Any]:
    episode = session.get(ReferralEpisode, episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="episode not found")
    before = _episode_dict(episode)
    updates = payload.model_dump(exclude_unset=True)
    mapping = {
        "ownerRole": "owner_role",
        "ownerName": "owner_name",
        "currentLocation": "current_location",
        "nextAction": "next_action",
        "consentStatus": "consent_status",
        "estimateStatus": "estimate_status",
        "insuranceStatus": "insurance_status",
        "pharmacyReady": "pharmacy_ready",
        "ownerUpdated": "owner_updated",
        "referringVetReportSent": "referring_vet_report_sent",
        "dischargeClear": "discharge_clear",
    }
    for key, value in updates.items():
        if key in {"actor", "note"}:
            continue
        setattr(episode, mapping.get(key, key), value)
    episode.updated_at = utc_now()
    session.add(episode)
    event = PatientWorkflowEvent(
        episode_id=episode.id,
        patient_case_id=episode.patient_case_id,
        event_type="state_change",
        action="update_episode_state",
        actor=auth.actor_name,
        note=payload.note or "episode state updated",
    )
    session.add(event)
    after = _episode_dict(episode)
    evidence, _ = create_evidence_event(
        session,
        event_type="patient_workflow_state",
        action="authenticated patient episode state updated",
        patient_case_id=episode.patient_case_id,
        referral_episode_id=episode.id,
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        previous_state=before,
        new_state=after,
        reason=payload.note or "authenticated episode state update",
        compliance_domain="clinical_governance",
        risk_level="red" if episode.blocker != "none" or episode.status == "blocked" else "amber",
        source_module="patient-care-v25-bridge",
        source_record_ref=episode.id,
        entity_type="referral_episode",
        entity_id=episode.id,
    )

    safety = None
    blocker = str(episode.blocker or "none")
    if blocker != "none" or episode.status == "blocked":
        source_ref = f"{episode.id}:{_slug(blocker)}"
        safety, _ = create_record(
            session,
            auth,
            {
                "recordType": "patient_safety",
                "domain": "patient",
                "confidentiality": "standard",
                "severity": "red",
                "title": f"Patient workflow blocker: {blocker}",
                "summary": payload.note or f"Patient episode is blocked by {blocker}",
                "patientRef": episode.patient_case_id,
                "episodeRef": episode.id,
                "sourceModule": "patient-care-blocker",
                "sourceRecordRef": source_ref,
                "immediateRisk": True,
                "safetyHoldRequested": True,
                "operationalImpact": {
                    "blocker": blocker,
                    "stage": episode.stage,
                    "location": episode.current_location,
                    "nextAction": episode.next_action,
                },
                "protectiveSummary": "Patient workflow held pending named review of a recorded blocker.",
                "owners": {
                    "clinical": {
                        "subject": auth.subject,
                        "name": auth.actor_name,
                        "role": auth.role,
                    }
                },
                "links": [
                    {
                        "entityType": "patient_workflow_event",
                        "entityRef": str(event.id or source_ref),
                        "relationship": "triggered_by",
                    },
                    {
                        "entityType": "evidence_event",
                        "entityRef": evidence.event_ref,
                        "relationship": "evidenced_by",
                    },
                ],
            },
        )
    session.commit()
    session.refresh(episode)
    return {
        "episode": _episode_dict(episode),
        "event": _workflow_event_dict(event),
        "safetyRecord": sensitive_record_dict(safety) if safety else None,
    }


@router.post("/api/patient-care/episodes/{episode_id}/events")
def secure_create_workflow_event(
    episode_id: str,
    payload: WorkflowEventCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CLINICAL_ROLE_TUPLE)),
) -> dict[str, Any]:
    episode = session.get(ReferralEpisode, episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="episode not found")
    before = _episode_dict(episode)
    event = PatientWorkflowEvent(
        episode_id=episode.id,
        patient_case_id=episode.patient_case_id,
        event_type=payload.eventType,
        action=payload.action,
        actor=auth.actor_name,
        note=payload.note,
        source_block_id=payload.sourceBlockId,
        at_time=payload.atTime,
    )
    episode.next_action = payload.note or payload.action.replace("_", " ")
    episode.updated_at = utc_now()
    session.add(episode)
    session.add(event)
    create_evidence_event(
        session,
        event_type="patient_workflow_event",
        action=payload.action,
        patient_case_id=episode.patient_case_id,
        referral_episode_id=episode.id,
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        previous_state=before,
        new_state=_episode_dict(episode),
        reason=payload.note,
        compliance_domain="clinical_governance",
        risk_level="amber",
        source_module="patient-care-v25-bridge",
        source_record_ref=episode.id,
        entity_type="patient_workflow_event",
        entity_id=str(event.id or payload.sourceBlockId or episode.id),
    )
    session.commit()
    session.refresh(event)
    return {"episode": _episode_dict(episode), "event": _workflow_event_dict(event)}


@router.post("/api/hr/fatigue/evaluate/{staff_member_id}")
def secure_evaluate_fatigue(
    staff_member_id: int,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLE_TUPLE)),
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=72)
    shifts = session.exec(
        select(Shift).where(Shift.staff_member_id == staff_member_id, Shift.starts_at >= since)
    ).all()
    on_call = session.exec(
        select(OnCallAssignment).where(
            OnCallAssignment.staff_member_id == staff_member_id,
            OnCallAssignment.starts_at >= since,
        )
    ).all()
    overtime = session.exec(
        select(OvertimeRequest).where(
            OvertimeRequest.staff_member_id == staff_member_id,
            OvertimeRequest.status == "approved",
        )
    ).all()
    shift_hours = sum(
        (shift.ends_at - shift.starts_at).total_seconds() / 3600
        for shift in shifts
        if shift.ends_at and shift.starts_at
    )
    overtime_hours = sum(item.hours for item in overtime)
    reasons: list[str] = []
    level = "LOW"
    if shift_hours > 55:
        level = "MED"
        reasons.append(f"{round(shift_hours, 1)} hours worked in 72h")
    if len(on_call) >= 3:
        level = "HIGH"
        reasons.append(f"{len(on_call)} on-call assignments in 72h")
    if overtime_hours > 12:
        level = "HIGH"
        reasons.append(f"{round(overtime_hours, 1)} overtime hours approved")
    risk = FatigueRiskRecord(
        staff_member_id=staff_member_id,
        risk_level=level,
        reasons=" | ".join(reasons) if reasons else "within threshold",
    )
    session.add(risk)
    session.flush()
    if level in {"MED", "HIGH"}:
        session.add(
            HRApprovalGate(
                gate_name="fatigue_risk",
                staff_member_id=staff_member_id,
                entity_type="fatigue",
                severity="red" if level == "HIGH" else "amber",
                reasons=risk.reasons,
            )
        )
        create_record(
            session,
            auth,
            {
                "recordType": "staff_welfare",
                "domain": "staff",
                "confidentiality": "restricted",
                "severity": "red" if level == "HIGH" else "amber",
                "title": "Staff fatigue and safe-cover review",
                "summary": risk.reasons,
                "affectedStaffSubject": f"staff-member:{staff_member_id}",
                "sourceModule": "hr-fatigue",
                "sourceRecordRef": f"fatigue-risk:{risk.id}",
                "immediateRisk": level == "HIGH",
                "safetyHoldRequested": level == "HIGH",
                "operationalImpact": {
                    "shiftHours72h": round(shift_hours, 1),
                    "onCallCount72h": len(on_call),
                    "approvedOvertimeHours": round(overtime_hours, 1),
                    "requiresCoverageReview": True,
                },
                "protectiveSummary": "Restricted workforce safety review may affect staffing availability.",
                "owners": {
                    "accountable": {
                        "subject": auth.subject,
                        "name": auth.actor_name,
                        "role": auth.role,
                    }
                },
            },
        )
    session.commit()
    return {
        "risk": {
            "id": risk.id,
            "staffMemberId": risk.staff_member_id,
            "riskLevel": risk.risk_level,
            "reasons": risk.reasons,
            "createdAt": risk.created_at.isoformat() if risk.created_at else None,
        },
        "summary": {
            "shift_hours_72h": round(shift_hours, 1),
            "on_call_count_72h": len(on_call),
            "approved_overtime_hours": round(overtime_hours, 1),
        },
    }


@router.post("/api/control-plane/handovers")
def secure_create_handover(
    payload: HandoverCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CLINICAL_ROLE_TUPLE)),
) -> dict[str, Any]:
    handover_ref = payload.handoverRef or f"handover-{int(utc_now().timestamp() * 1000000)}"
    if session.exec(select(AccountableHandover).where(AccountableHandover.handover_ref == handover_ref)).first():
        raise HTTPException(status_code=409, detail="handover_ref already exists")
    row = AccountableHandover(
        handover_ref=handover_ref,
        patient_case_id=payload.patientCaseId,
        referral_episode_id=payload.referralEpisodeId,
        from_actor=auth.actor_name,
        from_role=auth.role,
        to_actor=payload.toActor,
        to_role=payload.toRole,
        status="pending",
        summary=payload.summary,
        clinical_risks_json=__import__("json").dumps(payload.clinicalRisks),
        outstanding_actions_json=__import__("json").dumps(payload.outstandingActions),
        escalation_threshold=payload.escalationThreshold,
        due_at=payload.dueAt,
    )
    session.add(row)
    session.flush()
    evidence, _ = create_evidence_event(
        session,
        event_type="handover_created",
        action="authenticated accountable handover created",
        patient_case_id=payload.patientCaseId,
        referral_episode_id=payload.referralEpisodeId,
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        new_state=handover_dict(row),
        reason="responsibility transfer requires explicit acceptance",
        evidence_links=[{"type": "handover", "id": handover_ref}],
        compliance_domain="clinical_governance",
        risk_level="red" if payload.clinicalRisks else "amber",
        source_module="control-plane-v25-bridge",
        source_record_ref=handover_ref,
        entity_type="handover",
        entity_id=handover_ref,
        idempotency_key=f"handover:create:{handover_ref}",
    )
    row.evidence_event_ref = evidence.event_ref
    session.add(row)
    safety = None
    if payload.clinicalRisks:
        safety, _ = create_record(
            session,
            auth,
            {
                "recordType": "patient_safety",
                "domain": "patient",
                "confidentiality": "standard",
                "severity": "red",
                "title": "Clinical-risk handover awaiting acceptance",
                "summary": "; ".join(payload.clinicalRisks),
                "patientRef": payload.patientCaseId,
                "episodeRef": payload.referralEpisodeId,
                "sourceModule": "control-plane-handover",
                "sourceRecordRef": handover_ref,
                "immediateRisk": True,
                "safetyHoldRequested": False,
                "operationalImpact": {
                    "handoverStatus": "pending",
                    "toRole": payload.toRole,
                    "dueAt": payload.dueAt.isoformat() if payload.dueAt else None,
                },
                "protectiveSummary": "Clinical responsibility has not transferred until the named recipient accepts the handover.",
                "owners": {
                    "clinical": {
                        "subject": auth.subject,
                        "name": auth.actor_name,
                        "role": auth.role,
                    }
                },
                "links": [
                    {
                        "entityType": "handover",
                        "entityRef": handover_ref,
                        "relationship": "awaiting_acceptance",
                    }
                ],
            },
        )
    session.commit()
    session.refresh(row)
    return {
        "handover": handover_dict(row),
        "safetyRecord": sensitive_record_dict(safety) if safety else None,
    }


@router.patch("/api/control-plane/handovers/{handover_id}/decision")
def secure_decide_handover(
    handover_id: int,
    payload: HandoverDecision,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CLINICAL_ROLE_TUPLE)),
) -> dict[str, Any]:
    row = session.get(AccountableHandover, handover_id)
    if not row:
        raise HTTPException(status_code=404, detail="handover not found")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail="handover already decided")
    if row.to_actor and row.to_actor not in {auth.actor_name, auth.subject, auth.actor_id} and auth.role not in SENIOR_ROLES:
        raise HTTPException(status_code=403, detail="only the named recipient or a senior escalation role may decide this handover")
    decision_value = payload.decision.lower().strip()
    if decision_value not in {"accepted", "rejected", "escalated"}:
        raise HTTPException(status_code=400, detail="decision must be accepted, rejected or escalated")
    previous = handover_dict(row)
    row.status = decision_value
    row.accepted_by = auth.actor_name
    row.accepted_by_role = auth.role
    row.accepted_at = utc_now()
    row.decision_note = payload.note
    session.add(row)
    evidence, _ = create_evidence_event(
        session,
        event_type="handover_decision",
        action=f"handover {decision_value}",
        patient_case_id=row.patient_case_id,
        referral_episode_id=row.referral_episode_id,
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        previous_state=previous,
        new_state=handover_dict(row),
        reason="named recipient decision",
        justification=payload.note,
        evidence_links=[{"type": "handover", "id": row.handover_ref}],
        compliance_domain="clinical_governance",
        risk_level="green" if decision_value == "accepted" else "red",
        source_module="control-plane-v25-bridge",
        source_record_ref=row.handover_ref,
        causation_event_ref=row.evidence_event_ref,
        entity_type="handover",
        entity_id=row.handover_ref,
        idempotency_key=f"handover:decision:{row.handover_ref}:{decision_value}",
    )
    row.evidence_event_ref = evidence.event_ref
    safety = _safety_by_source(session, "control-plane-handover", row.handover_ref)
    escalation = None
    if safety:
        create_decision(
            session,
            safety,
            auth,
            decision_type="handover",
            decision=decision_value,
            reason=payload.note or f"handover {decision_value}",
            previous_state={"handover": previous},
            result_state={"handover": handover_dict(row)},
        )
        if decision_value in {"rejected", "escalated"}:
            escalation = create_escalation(
                session,
                safety,
                auth,
                {
                    "reason": payload.note or f"Clinical handover {decision_value}",
                    "to": {"role": "senior_clinician"},
                    "dueAt": row.due_at,
                },
            )
    session.commit()
    session.refresh(row)
    return {
        "handover": handover_dict(row),
        "safetyRecord": sensitive_record_dict(safety) if safety else None,
        "escalation": escalation_dict(escalation) if escalation else None,
    }


@router.post("/api/control-plane/critical-results")
def secure_create_critical_result(
    payload: CriticalResultCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CLINICAL_ROLE_TUPLE)),
) -> dict[str, Any]:
    if session.exec(
        select(CriticalResultAcknowledgement).where(CriticalResultAcknowledgement.result_ref == payload.resultRef)
    ).first():
        raise HTTPException(status_code=409, detail="result_ref already exists")
    row = CriticalResultAcknowledgement(
        result_ref=payload.resultRef,
        patient_case_id=payload.patientCaseId,
        referral_episode_id=payload.referralEpisodeId,
        result_type=payload.resultType,
        severity=payload.severity,
        summary=payload.summary,
        status="awaiting_acknowledgement",
        assigned_to=payload.assignedTo,
        assigned_role=payload.assignedRole,
        due_at=payload.dueAt,
    )
    session.add(row)
    session.flush()
    evidence, _ = create_evidence_event(
        session,
        event_type="critical_result_received",
        action="critical result awaiting human acknowledgement",
        patient_case_id=payload.patientCaseId,
        referral_episode_id=payload.referralEpisodeId,
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        new_state=critical_result_dict(row),
        reason=payload.summary,
        supervisor_required=True,
        supervisor_approval_status="pending",
        compliance_domain="diagnostics",
        risk_level="red",
        source_module="control-plane-v25-bridge",
        source_record_ref=payload.resultRef,
        entity_type="critical_result",
        entity_id=payload.resultRef,
        idempotency_key=f"critical-result:create:{payload.resultRef}",
    )
    row.evidence_event_ref = evidence.event_ref
    session.add(row)
    safety, _ = create_record(
        session,
        auth,
        {
            "recordType": "patient_safety",
            "domain": "patient",
            "confidentiality": "standard",
            "severity": "red",
            "title": f"Critical {payload.resultType} result awaiting acknowledgement",
            "summary": payload.summary,
            "patientRef": payload.patientCaseId,
            "episodeRef": payload.referralEpisodeId,
            "sourceModule": "control-plane-critical-result",
            "sourceRecordRef": payload.resultRef,
            "immediateRisk": True,
            "safetyHoldRequested": False,
            "operationalImpact": {
                "resultRef": payload.resultRef,
                "assignedTo": payload.assignedTo,
                "assignedRole": payload.assignedRole,
                "dueAt": payload.dueAt.isoformat() if payload.dueAt else None,
            },
            "protectiveSummary": "Critical result remains open until a named clinician acknowledges it and records action taken.",
            "owners": {
                "clinical": {
                    "subject": payload.assignedTo,
                    "name": payload.assignedTo,
                    "role": payload.assignedRole,
                }
            },
            "links": [
                {
                    "entityType": "critical_result",
                    "entityRef": payload.resultRef,
                    "relationship": "awaiting_acknowledgement",
                }
            ],
        },
    )
    session.commit()
    session.refresh(row)
    return {"result": critical_result_dict(row), "safetyRecord": sensitive_record_dict(safety)}


@router.patch("/api/control-plane/critical-results/{result_id}/acknowledge")
def secure_acknowledge_critical_result(
    result_id: int,
    payload: CriticalResultDecision,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CLINICAL_ROLE_TUPLE)),
) -> dict[str, Any]:
    row = session.get(CriticalResultAcknowledgement, result_id)
    if not row:
        raise HTTPException(status_code=404, detail="critical result not found")
    if row.status != "awaiting_acknowledgement":
        raise HTTPException(status_code=409, detail="critical result already acknowledged")
    if row.assigned_to and row.assigned_to not in {auth.actor_name, auth.subject, auth.actor_id} and auth.role not in SENIOR_ROLES:
        raise HTTPException(status_code=403, detail="only the assigned clinician or a senior escalation role may acknowledge this result")
    previous = critical_result_dict(row)
    row.status = "acknowledged"
    row.acknowledged_by = auth.actor_name
    row.acknowledged_at = utc_now()
    row.action_taken = payload.actionTaken
    session.add(row)
    evidence, _ = create_evidence_event(
        session,
        event_type="critical_result_acknowledged",
        action="critical result acknowledged and action recorded",
        patient_case_id=row.patient_case_id,
        referral_episode_id=row.referral_episode_id,
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        previous_state=previous,
        new_state=critical_result_dict(row),
        reason=row.summary,
        justification=payload.note or payload.actionTaken,
        compliance_domain="diagnostics",
        risk_level="green",
        source_module="control-plane-v25-bridge",
        source_record_ref=row.result_ref,
        causation_event_ref=row.evidence_event_ref,
        entity_type="critical_result",
        entity_id=row.result_ref,
        idempotency_key=f"critical-result:ack:{row.result_ref}",
    )
    row.evidence_event_ref = evidence.event_ref
    session.add(row)
    safety = _safety_by_source(session, "control-plane-critical-result", row.result_ref)
    action = None
    decision = None
    if safety:
        action = create_action(
            session,
            safety,
            auth,
            {
                "actionType": "clinical_review",
                "title": "Critical result acknowledged and action recorded",
                "description": payload.actionTaken,
                "owner": {"subject": auth.subject, "name": auth.actor_name, "role": auth.role},
                "requiresIndependentVerification": True,
            },
        )
        decision = complete_action(
            session,
            safety,
            action,
            auth,
            {
                "expectedVersion": action.version,
                "completionEvidence": payload.note or payload.actionTaken,
            },
        )
    session.commit()
    session.refresh(row)
    return {
        "result": critical_result_dict(row),
        "safetyRecord": sensitive_record_dict(safety) if safety else None,
        "action": action_dict(action) if action else None,
        "decision": decision_dict(decision) if decision else None,
    }
